Face Looker Web: Smooth Interaction Edition
这是一个基于 Web Canvas 的高性能人脸视线跟随交互 Demo。 本项目基于 face_looker 的 Sprite Sheet（网格图）生成理念，但在前端交互层进行了深度优化，实现了类生物的视觉惯性和自动归位机制，消除了传统实现的机械感和抖动。

核心理念：抛弃复杂的实时 3D 渲染，使用预渲染的 AI 高清网格图（Sprite Sheet），通过高性能的 Canvas 切片技术实现 0 延迟、高保真的视线跟随效果。

🌟 P0 版本核心改进 (Key Improvements)
相较于基础的鼠标跟随实现，本版本引入了以下 P0 级体验优化：

1. 视觉惯性系统 (Visual Inertia System)
改进前：人脸朝向绝对跟随鼠标，移动生硬，甚至在鼠标快速移动时产生“瞬移”和闪烁，机械感重。

改进后：引入 Lerp (线性插值) 物理算法。眼神的移动带有自然的阻尼感和加减速过程，模拟真实的头部转动惯量。

配置项：smoothing: 0.08 (数值越小越有重量感)

2. 生物感待机归位 (Alive Idle State)
改进前：鼠标移出或停止后，人脸僵硬地停留在最后一个角度。

改进后：内置空闲检测器。当用户停止交互超过设定时间（如 2秒）后，人脸会自动、缓慢地转回正前方注视屏幕，模拟生物的“注意力回归”本能。

3. 坐标逻辑修正 (Coordinate Correction)
改进前：存在由坐标系差异导致的“鼠标向上移，人脸向下看”的逻辑错误。

改进后：内置 Y 轴自动反转逻辑，并对齐了 Grid 图的行列映射，确保视线方向与鼠标位置绝对同步。

4. 极简架构 (Lightweight Architecture)
零依赖：移除了 face-api.js 等庞大的检测库。

纯 Canvas：直接解析 Grid 图片，内存占用极低，在移动端也能流畅运行 60FPS。

⚙️ 配置说明 (Configuration)
在 index.html 的 CONFIG 对象中，你可以根据 Grid 图的规格和交互需求进行微调：

const CONFIG = {
    // 网格图路径 (确保文件名后缀一致)
    imageSrc: './example_grid.webp', 
    
    // Grid 图的规格 (Replicate 生成通常为 11x11 或 7x7)
    rows: 11, 
    cols: 11,
    
    // [核心参数] 平滑系数 (0.01 - 1.0)
    // 0.05: 非常重，像慢镜头
    // 0.08: 丝般顺滑 (推荐)
    // 0.50: 反应极快，接近无延迟
    smoothing: 0.08, 

    // [核心参数] 空闲归位时间 (毫秒)
    // 鼠标静止多久后自动回正
    idleTime: 2000 
};

🛠️ 技术原理
Sprite Sheet 切片：加载一张包含 121 个不同角度人脸的大图（Grid）。

向量映射：将鼠标在屏幕上的 (x, y) 归一化坐标映射到 Grid 图对应的 (col, row) 索引。

物理循环：使用 requestAnimationFrame 运行物理引擎，计算当前帧与目标帧之间的插值。

Canvas 渲染：利用 ctx.drawImage 的裁剪参数，仅绘制当前计算出的那一帧切片到全屏画布。

📝 TODO
[ ] 增加移动端陀螺仪支持 (DeviceOrientation)。

[ ] 增加眨眼动画 (通过 Canvas 图层叠加模拟)。

[ ] 支持多状态切换 (如：开心、思考、休眠模式的 Grid 图切换)。