# LivePortrait 动物 Checkpoint 下载地址汇总

根据搜索结果，以下是 LivePortrait 动物模型的下载地址和方法：

## 🎯 推荐下载方式

### 1. HuggingFace（最推荐）

**仓库地址**: https://huggingface.co/Kijai/LivePortrait_safetensors

**下载方法**:
```python
# 在 Colab 或本地 Python 中
from huggingface_hub import hf_hub_download

# 下载模型文件
hf_hub_download(
    repo_id="Kijai/LivePortrait_safetensors",
    filename="liveportrait.safetensors",  # 根据实际文件名调整
    local_dir="checkpoints",
    local_dir_use_symlinks=False
)
```

**或者手动下载**:
1. 访问 https://huggingface.co/Kijai/LivePortrait_safetensors
2. 点击 "Files" 标签
3. 下载所有 `.safetensors` 文件
4. 将文件放到 `checkpoints/` 目录

### 2. 官方 GitHub 仓库

**仓库地址**: https://github.com/KwaiVGI/LivePortrait

**下载位置**:
- 查看仓库的 `pretrained_weights/` 目录
- 或查看 README 中的 "Model Zoo" 部分
- 可能有下载脚本或 Google Drive 链接

**注意**: 官方仓库可能没有直接提供动物 checkpoint，需要查看 issue 或社区讨论

### 3. 社区整合包（包含动物模型）

**来源 1**: AI应用帮
- 网站: https://aiyy.info/liveportrait/
- 提供包含动物模型的一键整合包
- 下载后解压，提取模型文件

**来源 2**: B站视频教程
- 搜索: "LivePortrait 动物模型整合包"
- 或访问: https://www.bilibili.com/video/BV1GE4m1d7Et/
- 视频描述中可能有下载链接

### 4. InsightFace 模型（必需依赖）

**下载地址**: https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip

**用途**: LivePortrait 需要 InsightFace 进行人脸/动物脸检测

**安装位置**: 
- 解压后放到 `ComfyUI/models/insightface/buffalo_l/` 目录
- 或根据 LivePortrait 文档要求放置

## 📝 在 Colab 中使用

我已经更新了 `colab_liveportrait_pet.ipynb`，其中包含了自动下载脚本。执行步骤 2 的单元格时，会自动尝试从 HuggingFace 下载。

如果自动下载失败，可以：

1. **手动上传到 Colab**:
   - 在 Colab 中点击左侧文件图标
   - 上传下载的 `.safetensors` 文件到 `checkpoints/` 目录

2. **使用 gdown（如果有 Google Drive 链接）**:
   ```python
   import gdown
   gdown.download("https://drive.google.com/uc?id=FILE_ID", "checkpoints/model.safetensors")
   ```

## 🔍 如何确认是否下载了动物模型

检查文件列表：
```bash
ls -lh checkpoints/
```

查找包含以下关键词的文件：
- `animal`
- `pet`
- `liveportrait_animal`
- 或查看文件大小（动物模型通常与基础模型大小相近）

## ⚠️ 重要提示

1. **模型格式**: 
   - 新版本可能使用 `.safetensors` 格式（更安全）
   - 旧版本可能使用 `.pth` 格式
   - 确保代码支持对应的格式

2. **模型兼容性**:
   - 不同版本的 LivePortrait 可能需要不同版本的 checkpoint
   - 建议使用与代码版本匹配的模型

3. **如果没有动物模型**:
   - 可以尝试使用基础模型（对动物支持有限）
   - 或寻找社区训练的动物 checkpoint
   - 或考虑使用替代方案（SadTalker 等）

## 🔗 相关链接

- [LivePortrait 官方 GitHub](https://github.com/KwaiVGI/LivePortrait)
- [HuggingFace 模型仓库](https://huggingface.co/Kijai/LivePortrait_safetensors)
- [InsightFace 下载](https://github.com/deepinsight/insightface/releases)
- [社区整合包](https://aiyy.info/liveportrait/)

## 💡 建议

1. **优先尝试 HuggingFace**: 通常是最新且最完整的资源
2. **检查官方仓库**: 查看最新的 README 和 issue
3. **社区资源**: 如果官方没有，社区整合包通常包含动物模型
4. **版本匹配**: 确保模型版本与代码版本兼容

如果以上方法都找不到，可以考虑：
- 使用基础模型（虽然对动物支持有限，但可能仍能工作）
- 使用替代方案（SadTalker、AnimateDiff 等）
- 在 GitHub issue 中询问社区
