"""
从单张宠物头像生成网格图 (纯几何变换版本)

用法示例：
    python simple_pet_grid.py --image inputs/pet_source.jpg --output outputs/grid_pet_7x7.webp --size 7

说明：
- 不依赖任何大模型，只用 OpenCV + PIL 做轻量的平移 / 旋转 / 轻微透视变换
- 生成 size×size 的网格图（默认 7×7），可直接喂给你现有的前端交互逻辑使用
"""

import argparse
import os
import math
import time

import cv2
import numpy as np
from PIL import Image
import json


def center_square_crop(img: Image.Image) -> Image.Image:
    """将输入图像裁成居中的正方形。"""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    right = left + side
    bottom = top + side
    return img.crop((left, top, right, bottom))


def generate_view_variants_on_patch(patch_img: Image.Image, grid_size: int = 7) -> list[Image.Image]:
    """
    对“头部区域 patch”生成略有不同的视角版本。

    注意：这里只处理头部小块，不负责背景。
    """
    # 统一将 patch 缩放到 256x256，保证后续运算和网格尺寸稳定
    target_side = 256
    if patch_img.size != (target_side, target_side):
        patch_img = patch_img.resize((target_side, target_side), Image.LANCZOS)

    w, h = patch_img.size
    base_np = cv2.cvtColor(np.array(patch_img), cv2.COLOR_RGB2BGR)

    variants = []

    # 最大平移和旋转幅度（可以根据效果调整）
    max_shift = 0.12  # 相对边长的最大平移比例
    max_angle = 12.0  # 最大旋转角度（度）

    for row in range(grid_size):
        for col in range(grid_size):
            # 归一化坐标 [-1, 1]
            # 行：0 -> 上，grid_size-1 -> 下
            ry = (row / (grid_size - 1)) * 2 - 1  # -1 (上) 到 1 (下)
            rx = (col / (grid_size - 1)) * 2 - 1  # -1 (左) 到 1 (右)

            # 计算平移像素
            shift_x = rx * max_shift * w
            shift_y = -ry * max_shift * h  # 上正下负，和鼠标逻辑类似

            # 计算旋转角度（左右 + 上下的一个线性组合）
            angle = rx * max_angle * 0.7 + ry * max_angle * 0.3

            # 构建仿射变换矩阵（先旋转再平移）
            center = (w / 2, h / 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            M[0, 2] += shift_x
            M[1, 2] += shift_y

            warped = cv2.warpAffine(
                base_np,
                M,
                (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )

            warped_pil = Image.fromarray(cv2.cvtColor(warped, cv2.COLOR_BGR2RGB))
            variants.append(warped_pil)

    return variants


def generate_frames_with_static_background(full_img: Image.Image, grid_size: int = 7) -> list[Image.Image]:
    """
    生成带静态背景的帧序列：
    - 背景：固定不动（整张图缩放到 512x512）
    - 头部：位于中心的一个正方形区域，仅对该区域做视角变换
    """
    # 背景缩放到 512x512，方便前端显示，也控制整体尺寸
    bg_side = 512
    bg = center_square_crop(full_img).resize((bg_side, bg_side), Image.LANCZOS)

    # 头部区域：中心 256x256
    head_side = 256
    head_left = (bg_side - head_side) // 2
    head_top = (bg_side - head_side) // 2
    head_box = (head_left, head_top, head_left + head_side, head_top + head_side)

    head_base = bg.crop(head_box)

    # 仅对头部 patch 生成视角变体
    head_variants = generate_view_variants_on_patch(head_base, grid_size=grid_size)

    frames: list[Image.Image] = []
    for hv in head_variants:
        frame = bg.copy()
        # 确保贴回时大小一致
        hv_resized = hv.resize((head_side, head_side), Image.LANCZOS)
        frame.paste(hv_resized, (head_left, head_top))
        frames.append(frame)

    return frames


def create_grid_from_images(images: list[Image.Image], output_path: str, grid_size: int) -> tuple[str, dict]:
    """将 images 列表拼接成 grid_size×grid_size 的网格图，并生成元数据。"""
    if not images:
        raise ValueError("没有可用图片生成网格图")

    cols = rows = grid_size
    w, h = images[0].size
    grid_w, grid_h = cols * w, rows * h

    grid_img = Image.new("RGB", (grid_w, grid_h))

    for idx, img in enumerate(images):
        if idx >= cols * rows:
            break
        c = idx % cols
        r = idx // cols
        grid_img.paste(img, (c * w, r * h))

    # 确保输出目录存在
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # 为了最大兼容性，这里统一保存为 JPG（Windows 照片应用和浏览器都支持）
    root, _ext = os.path.splitext(output_path)
    output_path = root + ".jpg"
    grid_img = grid_img.convert("RGB")
    grid_img.save(output_path, "JPEG", quality=90, optimize=True)

    meta = {
        "rows": rows,
        "cols": cols,
        "created_at": time.time(),
    }
    # 使用与图片同名但扩展名为 .json 的元数据文件
    root, _ext = os.path.splitext(output_path)
    meta_path = root + ".json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return output_path, meta


def main():
    parser = argparse.ArgumentParser(description="从单张宠物头像生成多视角网格图（轻量版）")
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="输入宠物头像路径，例如 inputs/pet_source.jpg",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/grid_pet_7x7.webp",
        help="输出网格图路径（默认: outputs/grid_pet_7x7.webp）",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=7,
        help="网格大小 N，生成 N×N 视角（默认 7）",
    )

    args = parser.parse_args()

    if not os.path.exists(args.image):
        raise FileNotFoundError(f"找不到输入图片: {args.image}")

    print(">>> 正在读取输入图片:", args.image)
    img = Image.open(args.image).convert("RGB")

    print(f">>> 生成 {args.size}x{args.size} 视角变体（静态背景，仅头部运动）...")
    frames = generate_frames_with_static_background(img, grid_size=args.size)

    print(">>> 拼接网格图...")
    grid_path, meta = create_grid_from_images(frames, args.output, grid_size=args.size)

    print("\n🎉 完成！")
    print("网格图路径:", grid_path)
    print("网格尺寸: {rows}x{cols}".format(**meta))
    print("元数据:", grid_path.replace(".webp", ".json"))


if __name__ == "__main__":
    main()


