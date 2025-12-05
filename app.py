import os
import time
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

def process_prediction_output(prediction):
    """封装好的处理逻辑，供正常流程和调试流程复用"""
    output = prediction.output
    if not output:
            raise Exception("任务显示成功但没有返回 Output 数据")

    print(">>> 生成结果:", output)

    # --- 兼容性处理与类型修复 ---
    # 1. 如果是列表，说明是多图模式
    if isinstance(output, list):
        print(f">>> 检测到多张图片 ({len(output)} 张)，正在进行 Grid 拼接...")
        url_list = [str(item) for item in output]
        grid_url = create_grid_from_urls(url_list)
        
    # 2. 如果是字典，说明是标准模式
    elif isinstance(output, dict) and 'grid' in output:
        grid_url_raw = output['grid']
        grid_url = str(grid_url_raw) # FileOutput -> 'https://...'
        
        if not grid_url:
                raise Exception("Output['grid'] 为空")
                
        local_url = download_image(grid_url)
        grid_url = local_url 
    else:
        raise Exception(f"未知的 Output 格式: {output}")

    return grid_url

@app.route('/api/debug_recover', methods=['GET'])
def debug_recover():
    """
    调试接口：通过任务 ID 恢复并展示结果
    用法：访问 http://localhost:5000/api/debug_recover?id=您的任务ID
    """
    task_id = request.args.get('id')
    if not task_id:
        return jsonify({'error': '请提供任务 ID, 例如 ?id=xxxxx'}), 400
        
    try:
        print(f">>> [DEBUG] 正在尝试恢复任务: {task_id}")
        prediction = replicate.predictions.get(task_id)
        
        if prediction.status == "succeeded":
            # 复用修复后的处理逻辑
            grid_url = process_prediction_output(prediction)
            return jsonify({'grid_url': grid_url, 'status': 'recovered'})
        else:
            return jsonify({'error': f"任务状态不是 succeeded，当前状态: {prediction.status}"}), 400
            
    except Exception as e:
        print(f">>> [DEBUG] 恢复失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    try:
        temp_path = "temp_input.jpg"
        file.save(temp_path)

        print(">>> 正在提交任务到 Replicate API...")
        
        try:
            prediction = replicate.predictions.create(
                version="kylan02/face-looker",
                input={
                    "image": open(temp_path, "rb"),
                    "step": 3,
                    "min_value": -15,
                    "max_value": 15
                }
            )
        except Exception as e:
            if "429" in str(e):
                return jsonify({'error': 'Replicate API 限流 (Rate Limit Exceeded)，请等待 1 分钟后再试。'}), 429
            raise e

        print(f">>> 任务已提交! ID: {prediction.id}")
        print(f">>> 可以在此处查看详情: https://replicate.com/p/{prediction.id}")

        last_status = prediction.status
        retry_count = 0
        MAX_RETRIES = 10

        while prediction.status not in ["succeeded", "failed", "canceled"]:
            try:
                prediction.reload()
                retry_count = 0 
            except Exception as e:
                print(f"\n>>> 警告: 获取状态失败 ({str(e)})，正在重试...")
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    raise Exception("多次重试获取状态失败，任务可能已丢失或网络异常。")
                time.sleep(min(2 ** retry_count, 10)) 
                continue

            if prediction.status != last_status:
                print(f">>> 当前状态: {prediction.status.upper()}")
                last_status = prediction.status
            
            if prediction.status == "processing":
                print(".", end="", flush=True)
            
            time.sleep(1.0)

        print("\n>>> 任务结束。最终状态:", prediction.status)

        if prediction.status == "succeeded":
            # 调用封装好的处理逻辑
            grid_url = process_prediction_output(prediction)
            return jsonify({'grid_url': grid_url})
        else:
            error_msg = f"任务失败: {prediction.error}"
            print(">>> Error:", error_msg)
            return jsonify({'error': error_msg}), 500

    except Exception as e:
        print(">>> Exception Error:", str(e))
        return jsonify({'error': str(e)}), 500

def download_image(url):
    """辅助函数：下载单张图片到 outputs"""
    try:
        # 确保 URL 是字符串
        url = str(url)
        filename = f"grid_{int(time.time())}.webp"
        save_path = os.path.join(OUTPUT_DIR, filename)
        resp = requests.get(url)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            print(f">>> 图片已保存至: {save_path}")
            return f"/{save_path}".replace("\\", "/") # 统一使用正斜杠
    except Exception as e:
        print(f"下载失败: {e}")
    return url

def create_grid_from_urls(url_list):
    """核心函数：下载多张小图并拼贴成 Grid"""
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

    cols = 11
    rows = 11
    
    single_w, single_h = images[0].size
    grid_w = cols * single_w
    grid_h = rows * single_h
    
    print(f">>> 开始拼接: 单图尺寸 {single_w}x{single_h}, 总尺寸 {grid_w}x{grid_h}")
    
    grid_img = Image.new('RGB', (grid_w, grid_h))
    
    for index, img in enumerate(images):
        if index >= cols * rows: break
        col = index % cols
        row = index // cols
        grid_img.paste(img, (col * single_w, row * single_h))

    filename = f"grid_stitched_{int(time.time())}.webp"
    save_path = os.path.join(OUTPUT_DIR, filename)
    
    grid_img.save(save_path, 'WEBP', quality=85)
    print(f">>> 拼接完成! 已保存至: {save_path}")
    
    return "/" + save_path.replace("\\", "/")

if __name__ == '__main__':
    print("服务器启动: http://localhost:5000")
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)
