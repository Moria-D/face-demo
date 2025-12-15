import os
import time
import json
import math
import requests
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

    grid_url_final = ""
    # 如果没传 input_step，尝试从 prediction.input 里拿（如果有）
    # 但通常我们在 generate 里知道 step 是多少
    step = input_step if input_step else 5 

    # --- 兼容性处理与类型修复 ---
    if isinstance(output, list):
        print(f">>> 检测到多张图片 ({len(output)} 张)，正在进行 Grid 拼接...")
        url_list = [str(item) for item in output]
        grid_url_final = create_grid_from_urls(url_list, step)
        
    elif isinstance(output, dict) and 'grid' in output:
        grid_url_raw = output['grid']
        grid_url = str(grid_url_raw)
        
        if not grid_url:
                raise Exception("Output['grid'] 为空")
                
        local_url = download_image(grid_url, step)
        grid_url_final = local_url 
    else:
        raise Exception(f"未知的 Output 格式: {output}")

    # 返回 URL 和 元数据
    # 为了方便，我们在 URL 后附带 query param? 或者让前端再次请求?
    # 最简单：generate 接口直接返回 meta 对象
    
    # 重新计算一下 meta 用于返回
    grid_size = math.ceil(30.0 / step + 1)
    return grid_url_final, {"rows": grid_size, "cols": grid_size}

@app.route('/api/debug_recover', methods=['GET'])
def debug_recover():
    task_id = request.args.get('id')
    if not task_id:
        return jsonify({'error': '请提供任务 ID'}), 400
    try:
        prediction = replicate.predictions.get(task_id)
        if prediction.status == "succeeded":
            # 尝试从 input 获取 step，默认 5
            step = 5
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

    # 设定 Step
    STEP = 5 

    try:
        temp_path = "temp_input.jpg"
        file.save(temp_path)

        print(">>> 正在提交任务到 Replicate API...")
        
        try:
            prediction = replicate.predictions.create(
                version="kylan02/face-looker",
                input={
                    "image": open(temp_path, "rb"),
                    "step": STEP, 
                    "min_value": -15,
                    "max_value": 15
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

def create_grid_from_urls(url_list, step=5):
    """拼接图片并保存元数据"""
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
            
    if not images:
        raise Exception("没有下载到任何有效图片")

    # 根据 step 动态计算行列
    grid_size = math.ceil(30.0 / step + 1)
    cols = grid_size
    rows = grid_size
    
    single_w, single_h = images[0].size
    grid_w = cols * single_w
    grid_h = rows * single_h
    
    print(f">>> 开始拼接: {cols}x{rows}, 单图 {single_w}x{single_h}")
    
    grid_img = Image.new('RGB', (grid_w, grid_h))
    
    for index, img in enumerate(images):
        if index >= cols * rows: break
        col = index % cols
        row = index // cols
        grid_img.paste(img, (col * single_w, row * single_h))

    timestamp = int(time.time())
    filename = f"grid_stitched_{timestamp}.webp"
    save_path = os.path.join(OUTPUT_DIR, filename)
    
    grid_img.save(save_path, 'WEBP', quality=85)
    print(f">>> 拼接完成! 已保存至: {save_path}")
    
    # 保存元数据
    save_metadata(f"grid_stitched_{timestamp}", step)
    
    return "/" + save_path.replace("\\", "/")

if __name__ == '__main__':
    print("服务器启动: http://localhost:5000")
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)
