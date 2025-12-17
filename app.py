import os
import time
import json
import math
import requests
import cv2
import numpy as np
from io import BytesIO
from PIL import Image

# 确保已设置 Token
if not os.environ.get("REPLICATE_API_TOKEN"):
    print("Warning: REPLICATE_API_TOKEN not found in environment variables.")
    # 请在本地环境变量中设置，不要上传到 GitHub
    # os.environ["REPLICATE_API_TOKEN"] = "your_token_here"

print("Starting app...")
from flask import Flask, request, jsonify, send_from_directory
import replicate

app = Flask(__name__, static_folder='.') 
OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取所有已生成的历史 Grid 图片列表，并尝试读取 metadata"""
    try:
        if not os.path.exists(OUTPUT_DIR):
            return jsonify([])
            
        files = []
        for f in sorted(os.listdir(OUTPUT_DIR), key=lambda x: os.path.getmtime(os.path.join(OUTPUT_DIR, x)), reverse=True):
            if f.endswith(('.webp', '.jpg', '.png')):
                # 尝试读取同名的 .json 元数据
                meta_file = os.path.splitext(f)[0] + '.json'
                meta_path = os.path.join(OUTPUT_DIR, meta_file)
                meta = {}
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, 'r') as mf:
                            meta = json.load(mf)
                    except:
                        pass
                
                files.append({
                    'name': f,
                    'url': f'/{OUTPUT_DIR}/{f}',
                    'time': time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(os.path.join(OUTPUT_DIR, f)))),
                    'meta': meta # 返回元数据
                })
        return jsonify(files)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/<name>', methods=['DELETE'])
def delete_history_item(name):
    """删除指定的历史文件及其元数据"""
    # 简单防护，避免路径穿越
    if ".." in name or "/" in name or "\\" in name:
        return jsonify({'error': '非法文件名'}), 400
    try:
        img_path = os.path.join(OUTPUT_DIR, name)
        if not os.path.exists(img_path):
            return jsonify({'error': '文件不存在'}), 404

        # 删除图片
        os.remove(img_path)

        # 删除同名元数据
        meta_path = os.path.join(OUTPUT_DIR, os.path.splitext(name)[0] + ".json")
        if os.path.exists(meta_path):
            os.remove(meta_path)

        return jsonify({'message': 'deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def save_metadata(filename_base, step):
    """辅助函数：保存元数据"""
    try:
        # 计算 rows/cols
        # range = 30 (-15~15), steps = 30/step + 1
        # 但如果是 11x11, step=3 (30/3+1=11)
        # 如果是 7x7, step=5 (30/5+1=7)
        # 简单算法：ceil(30/step + 1)
        grid_size = math.ceil(30.0 / step + 1)
        
        meta = {
            "step": step,
            "rows": grid_size,
            "cols": grid_size,
            "created_at": time.time()
        }
        
        meta_path = os.path.join(OUTPUT_DIR, filename_base + ".json")
        with open(meta_path, 'w') as f:
            json.dump(meta, f)
        print(f">>> 元数据已保存: {meta_path}")
        return meta
    except Exception as e:
        print(f"元数据保存失败: {e}")
        return {}

def process_prediction_output(prediction, input_step=None):
    """封装好的处理逻辑"""
    output = prediction.output
    if not output:
            raise Exception("任务显示成功但没有返回 Output 数据")

    print(">>> 生成结果:", output)

    if not output:
        # 尝试 reload 一次，有时候 status=succeeded 但 output 还没同步
        print(">>> Output 为空，尝试重新 reload prediction...")
        prediction.reload()
        output = prediction.output
        print(">>> Reload 后结果:", output)

    if not output:
            # 可能是人脸检测失败，LivePortrait 有时候对无法检测人脸的图会静默失败或返回空
            raise Exception("任务成功但没有返回 Output (可能是未检测到人脸，请换一张正脸照片试)")
    # 如果没传 input_step，尝试从 prediction.input 里拿（如果有）
    # 但通常我们在 generate 里知道 step 是多少
    step = input_step if input_step else 3 

    # --- 兼容性处理与类型修复 ---
    if isinstance(output, list):
        print(f">>> 检测到列表输出 ({len(output)} 项)，检查内容类型...")
        # LivePortrait 有时返回 [url] 列表，有时直接返回 url
        if len(output) > 0:
            first_item = str(output[0])
            if first_item.endswith('.mp4') or 'replicate.delivery' in first_item:
                print(">>> 识别为视频 URL 列表，取第一个作为视频源...")
                return process_prediction_output_video(first_item, step)
            else:
                 # 假设是图片列表，走旧逻辑
                 print(">>> 识别为图片列表，进行拼接...")
            url_list = [str(item) for item in output]
            grid_url_final = create_grid_from_urls(url_list, step)
        else:
            raise Exception("Output 列表为空")
        
    elif isinstance(output, str) and (output.endswith('.mp4') or output.startswith('http')):
        print(">>> 检测到单视频输出...")
        return process_prediction_output_video(output, step)
        
    else:
        # Fallback
        raise Exception(f"未知的 Output 格式: {output}")

    # 返回 URL 和 元数据
    grid_size = math.ceil(30.0 / step + 1)
    return grid_url_final, {"rows": grid_size, "cols": grid_size}

def process_prediction_output_video(video_url, step):
    """专门处理视频输出的逻辑"""
    print(f">>> 正在处理视频转网格: {video_url}")
    # 下载视频到临时文件
    temp_video_path = "temp_output.mp4"
    resp = requests.get(video_url)
    with open(temp_video_path, 'wb') as f:
        f.write(resp.content)
    
    # 提取帧
    grid_dim = math.ceil(30.0 / step + 1)
    target_count = grid_dim * grid_dim
    
    frames = extract_frames_from_video(temp_video_path, target_count)
    # driving_video.mp4 由 `grid_to_video.py` 以“蛇形扫描”生成，因此输出视频帧序也会是蛇形；
    # 拼接网格时需要把蛇形顺序还原成标准网格，否则前端映射会呈“S 型”且静止回中不正确。
    return create_grid_from_pil_images(frames, step, rows=grid_dim, cols=grid_dim, input_order="snake")

@app.route('/api/debug_recover', methods=['GET'])
def debug_recover():
    task_id = request.args.get('id')
    if not task_id:
        return jsonify({'error': '请提供任务 ID'}), 400
    try:
        prediction = replicate.predictions.get(task_id)
        if prediction.status == "succeeded":
            # 尝试从 input 获取 step，默认 5
            step = 3
            if prediction.input and 'step' in prediction.input:
                step = int(prediction.input['step'])
                
            grid_url, meta = process_prediction_output(prediction, step)
            return jsonify({'grid_url': grid_url, 'meta': meta, 'status': 'recovered'})
        else:
            return jsonify({'error': f"任务状态不是 succeeded: {prediction.status}"}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    # 设定 Step（3 => 11x11 网格）
    STEP = 3 

    try:
        temp_path = "temp_input.jpg"
        file.save(temp_path)

        print(">>> 正在提交任务到 Replicate API (LivePortrait)...")
        
        try:
            # 动态获取最新版本，避免 ID 硬编码失效
            model = replicate.models.get("fofr/live-portrait")
            latest_version = model.latest_version
            print(f">>> 使用模型版本: {latest_version.id}")

            prediction = replicate.predictions.create(
                version=latest_version,
                input={
                    # LivePortrait 的参数名经常变动，有些版本是 source_image，有些是 face_image
                    # 现在的报错提示 input: face_image is required，说明是 face_image
                    "face_image": open(temp_path, "rb"),
                    "driving_video": open("driving_video.mp4", "rb"),
                    "flag_relative_motion": True,
                    "flag_do_crop": True
                }
            )
        except Exception as e:
            if "429" in str(e):
                return jsonify({'error': 'Replicate API 限流，请等待 1 分钟后再试。'}), 429
            raise e

        print(f">>> 任务已提交! ID: {prediction.id}")
        
        last_status = prediction.status
        retry_count = 0
        MAX_RETRIES = 10

        while prediction.status not in ["succeeded", "failed", "canceled"]:
            try:
                prediction.reload()
                retry_count = 0 
            except Exception as e:
                print(f"\n>>> 警告: 获取状态失败，正在重试...")
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    raise Exception("多次重试获取状态失败")
                time.sleep(min(2 ** retry_count, 10)) 
                continue

            if prediction.status != last_status:
                print(f">>> 当前状态: {prediction.status.upper()}")
                last_status = prediction.status
            
            if prediction.status == "processing":
                print(".", end="", flush=True)
            
            time.sleep(5.0)

        print("\n>>> 任务结束。最终状态:", prediction.status)

        if prediction.status == "succeeded":
            grid_url, meta = process_prediction_output(prediction, STEP)
            # 返回 URL 和 Meta
            return jsonify({'grid_url': grid_url, 'meta': meta})
        else:
            error_msg = f"任务失败: {prediction.error}"
            print(">>> Error:", error_msg)
            return jsonify({'error': error_msg}), 500

    except Exception as e:
        print(">>> Exception Error:", str(e))
        return jsonify({'error': str(e)}), 500

def download_image(url, step=5):
    """下载图片并保存元数据"""
    try:
        url = str(url)
        timestamp = int(time.time())
        filename = f"grid_{timestamp}.webp"
        save_path = os.path.join(OUTPUT_DIR, filename)
        resp = requests.get(url)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            print(f">>> 图片已保存至: {save_path}")
            
            # 保存元数据
            save_metadata(f"grid_{timestamp}", step)
            
            return f"/{save_path}".replace("\\", "/") 
    except Exception as e:
        print(f"下载失败: {e}")
    return url


def create_grid_from_pil_images(images, step=5, rows=None, cols=None, input_order="row-major"):
    """从 PIL Image 列表创建网格图

    - rows/cols: 若传入则按指定网格拼接，否则按 sqrt(len(images)) 推断
    - input_order:
        - "row-major": images 顺序为按行从左到右、从上到下
        - "snake": images 顺序为蛇形扫描（偶数行左->右，奇数行右->左），拼接时会还原为标准网格
    """
    if not images:
        raise Exception("没有有效的图片用于拼接")

    count = len(images)
    if rows is None or cols is None:
        # 尝试寻找最接近的方形
        grid_size = math.ceil(math.sqrt(count))
        cols = grid_size
        rows = grid_size
    
    single_w, single_h = images[0].size
    grid_w = cols * single_w
    grid_h = rows * single_h
    
    print(f">>> 开始拼接: {cols}x{rows}, 总帧数: {count}, 单图 {single_w}x{single_h}")
    
    grid_img = Image.new('RGB', (grid_w, grid_h))
    
    for index, img in enumerate(images):
        if index >= cols * rows:
            break
        row = index // cols
        col_in_row = index % cols
        if input_order == "snake" and (row % 2 == 1):
            col = cols - 1 - col_in_row
        else:
            col = col_in_row
        grid_img.paste(img, (col * single_w, row * single_h))

    timestamp = int(time.time())
    filename = f"grid_stitched_{timestamp}.webp"
    save_path = os.path.join(OUTPUT_DIR, filename)
    
    grid_img.save(save_path, 'WEBP', quality=85)
    print(f">>> 拼接完成! 已保存至: {save_path}")
    
    # 保存元数据
    # 这里我们修正一下 meta 的 rows/cols 为实际的
    meta = {
        "step": step,
        "rows": rows,
        "cols": cols,
        "created_at": time.time()
    }
    meta_path = os.path.join(OUTPUT_DIR, f"grid_stitched_{timestamp}.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f)
    
    return "/" + save_path.replace("\\", "/"), meta

def extract_frames_from_video(video_path, target_count=49):
    """从视频中提取指定数量的帧"""
    print(f">>> 正在从视频提取帧: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception("无法打开视频文件")
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"    视频总帧数: {total_frames}, 目标帧数: {target_count}")
    
    images = []
    
    if total_frames <= 0:
         # Fallback if frame count not available
         success = True
         while success:
             success, frame = cap.read()
             if success:
                 img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                 images.append(img)
    else:
        # 均匀采样
        indices = np.linspace(0, total_frames - 1, target_count, dtype=int)
        for i in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                images.append(img)
            else:
                print(f"    警告: 无法读取第 {i} 帧")
                
    cap.release()
    
    if len(images) == 0:
        raise Exception("未提取到任何帧")
        
    # 如果提取多了(比如 fallback 读了全部)，进行采样
    if len(images) > target_count:
        indices = np.linspace(0, len(images) - 1, target_count, dtype=int)
        images = [images[i] for i in indices]
        
    return images

def create_grid_from_urls(url_list, step=3):
    """拼接图片并保存元数据 (旧接口兼容)"""
    images = []
    print(">>> 正在下载子图片...")
    
    for i, url in enumerate(url_list):
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content))
                images.append(img)
            else:
                print(f"警告: 第 {i} 张图片下载失败")
        except Exception as e:
            print(f"警告: 下载异常 {e}")
            
    grid_url, meta = create_grid_from_pil_images(images, step)
    # 旧接口只返回 url
    return grid_url

if __name__ == '__main__':
    print("服务器启动: http://localhost:5000")
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)
