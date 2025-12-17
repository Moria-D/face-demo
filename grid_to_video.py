import cv2
import numpy as np
import os
import math
from PIL import Image

def grid_to_video(grid_path, output_path="driving_video.mp4", rows=11, cols=11, fps=10):
    """
    将网格图转换为视频，采用蛇形扫描以保证动作连续性。
    """
    if not os.path.exists(grid_path):
        print(f"错误: 找不到文件 {grid_path}")
        return

    print(f"正在读取网格图: {grid_path}...")
    try:
        # 使用 PIL 读取图片 (兼容 WebP/JPG)
        full_img = Image.open(grid_path)
        full_img = full_img.convert('RGB')
        width, height = full_img.size
        
        # 计算单个小格子的尺寸
        cell_w = width // cols
        cell_h = height // rows
        print(f"网格尺寸: {width}x{height}, 单格尺寸: {cell_w}x{cell_h}, 布局: {rows}x{cols}")

        frames = []
        
        # 遍历网格
        for r in range(rows):
            # 蛇形扫描：偶数行从左到右，奇数行从右到左
            col_range = range(cols) if r % 2 == 0 else range(cols - 1, -1, -1)
            
            for c in col_range:
                left = c * cell_w
                upper = r * cell_h
                right = left + cell_w
                lower = upper + cell_h
                
                # 切割图片
                crop = full_img.crop((left, upper, right, lower))
                # 转换为 OpenCV 格式 (RGB -> BGR)
                frame_np = cv2.cvtColor(np.array(crop), cv2.COLOR_RGB2BGR)
                frames.append(frame_np)

        # 视频编码器设置
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        out = cv2.VideoWriter(output_path, fourcc, fps, (cell_w, cell_h))

        print(f"正在合成视频，共 {len(frames)} 帧...")
        for frame in frames:
            out.write(frame)

        out.release()
        print(f"✅ 成功! 驱动视频已保存为: {output_path}")
        print("💡 提示: 现在你可以将此视频作为 'Driving Video' 上传到 LivePortrait 了。")

    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    # --- 配置区域 ---
    
    # 这里填写你现有的 121 格图的路径
    target_file = r"outputs\grid_woman.webp" # 使用 r 前缀防止转义
    output_dir = "outputs"
    
    # 如果没指定 target_file 或者指定的文件不存在，则自动查找
    if not target_file or not os.path.exists(target_file):
        if os.path.exists(output_dir):
            files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(('.webp', '.jpg', '.png'))]
            # 按大小排序，通常 121 格图比 25/49 格图大
            files.sort(key=lambda x: os.path.getsize(x), reverse=True)
            if files:
                target_file = files[0]
                print(f"自动选择最大的网格图: {target_file}")
            
    if not target_file:
        # 如果找不到，请手动指定路径
        target_file = "input_grid.webp" 
        print(f"未自动找到网格图，尝试读取默认路径: {target_file}")

    # 11x11 = 121 张
    ROWS = 11
    COLS = 11
    
    # 也可以手动覆盖路径
    # target_file = "C:/Users/Administrator/Desktop/face_demo/outputs/grid_1764922544.webp"
    
    grid_to_video(target_file, rows=ROWS, cols=COLS)

