# Document PDF Export - Implementation & Installation Guide

本文档涵盖文档 PDF 导出功能的实现细节和安装步骤 (支持简历、求职信等多种文档类型)。

---

## 目录

- [功能概览](#功能概览)
- [系统架构](#系统架构)
- [安装指南](#安装指南)
- [使用方法](#使用方法)
- [添加新模板](#添加新模板)
- [配置说明](#配置说明)
- [故障排除](#故障排除)
- [性能优化](#性能优化)
- [参考资料](#参考资料)

---

## 功能概览

使用 **weasyprint** 实现的通用文档 PDF 导出功能。

### 核心特性

- ✅ 多文档类型支持 (resume, cover_letter 等)
- ✅ Markdown → PDF 转换
- ✅ 每种文档类型独立模板 (modern/classic/minimal)
- ✅ 中文字体支持
- ✅ CSS 样式控制
- ✅ 模板自动发现
- ✅ 可配置字号
- ✅ 可选生成时间戳
- ✅ 易于扩展新文档类型

---

## 系统架构

### 目录结构

```
backend/app/modules/resumes/
├── export/
│   ├── __init__.py          # 公开接口
│   ├── service.py           # 通用文档导出服务 (DocumentExportService)
│   ├── generator.py         # PDF 生成器 (PDFGenerator, 支持多文档类型)
│   ├── renderer.py          # Markdown → HTML (MarkdownRenderer)
│   └── templates/           # Jinja2 HTML 模板 (按文档类型分类)
│       ├── resume/          # 简历模板
│       │   ├── modern.html
│       │   ├── classic.html
│       │   └── minimal.html
│       └── cover_letter/    # 求职信模板 (待创建)
│           ├── modern.html
│           ├── classic.html
│           └── minimal.html
├── static/
│   ├── css/                 # 样式文件 (按文档类型分类)
│   │   ├── resume/          # 简历样式
│   │   │   ├── base.css     # 基础样式 + 字体
│   │   │   ├── modern.css
│   │   │   ├── classic.css
│   │   │   └── minimal.css
│   │   └── cover_letter/    # 求职信样式 (待创建)
│   │       ├── base.css
│   │       └── ...
│   └── fonts/               # 中文字体 (所有文档类型共享)
│       ├── NotoSansSC-Regular.ttf  # 需手动下载
│       ├── NotoSansSC-Bold.ttf
│       └── NotoSerifSC-Regular.ttf
├── schemas.py               # Pydantic 数据模型
├── service.py               # ResumeService (调用 DocumentExportService)
└── router.py                # Resume API 端点
```

### 技术栈

- **weasyprint** - HTML/CSS → PDF 渲染引擎
- **markdown2** - Markdown → HTML 转换
- **jinja2** - HTML 模板引擎

### 架构设计 (方案 3: 混合方案)

**通用导出服务 + 业务模块适配器**

```
DocumentExportService (通用)
        ↓
    PDFGenerator (支持 document_type 参数)
        ↓
    templates/{document_type}/{template_name}.html
    css/{document_type}/{template_name}.css

业务模块适配:
- ResumeService → DocumentExportService(document_type="resume")
- CoverLetterService → DocumentExportService(document_type="cover_letter")
```

**优点:**
- ✅ 导出逻辑完全通用,易于扩展
- ✅ 业务模块保持独立
- ✅ API 语义清晰 (/resumes/{id}/export, /cover-letters/{id}/export)
- ✅ 模板和样式按文档类型隔离,互不干扰

---

## 安装指南

### 步骤 1: 安装 Python 依赖

#### 使用 uv (推荐)

```bash
cd backend
uv add weasyprint markdown2 jinja2
uv sync
```

#### 手动添加

在 `pyproject.toml` 中添加:

```toml
[project]
dependencies = [
    # ... 现有依赖 ...
    "weasyprint>=62.0",
    "markdown2>=2.4.0",
    "jinja2>=3.1.0",
]
```

然后运行: `uv sync`

---

### 步骤 2: 安装系统依赖

#### Windows

1. 下载 GTK3 Runtime:
   - https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
   - 下载最新 `.exe` 安装器

2. 运行安装器 (使用默认设置)

3. 验证安装:
   ```powershell
   python -c "import weasyprint; print(weasyprint.__version__)"
   ```

#### macOS

```bash
brew install cairo pango gdk-pixbuf libffi
python -c "import weasyprint; print(weasyprint.__version__)"
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info

python -c "import weasyprint; print(weasyprint.__version__)"
```

#### Docker

在 `Dockerfile` 中添加:

```dockerfile
# 安装 weasyprint 系统依赖
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
```

---

### 步骤 3: 下载和配置字体

#### 下载 Noto 字体

1. **Noto Sans SC** (无衬线,现代风格)
   - 访问: https://fonts.google.com/noto/specimen/Noto+Sans+SC
   - 点击 "Download family"
   - 解压后找到: `NotoSansSC-Regular.ttf` 和 `NotoSansSC-Bold.ttf`

2. **Noto Serif SC** (衬线,传统风格)
   - 访问: https://fonts.google.com/noto/specimen/Noto+Serif+SC
   - 点击 "Download family"
   - 解压后找到: `NotoSerifSC-Regular.ttf`

#### 放置字体文件

```bash
# 在 backend 目录下
mkdir -p app/modules/resumes/static/fonts

# 将下载的 3 个字体文件复制到该目录:
# - NotoSansSC-Regular.ttf
# - NotoSansSC-Bold.ttf
# - NotoSerifSC-Regular.ttf
```

#### 验证字体

```bash
ls -la app/modules/resumes/static/fonts/
# 应该看到 3 个 .ttf 文件
```

#### 字体配置说明

字体在 `static/css/base.css` 中通过 `@font-face` 声明:

```css
@font-face {
    font-family: 'Noto Sans SC';
    src: url('../fonts/NotoSansSC-Regular.ttf') format('truetype');
    font-weight: 400;
    font-style: normal;
}
```

**添加自定义字体:**
1. 下载 `.ttf` 文件
2. 放入 `static/fonts/`
3. 在 CSS 中添加 `@font-face` 声明
4. 在模板 CSS 中使用

---

### 步骤 4: 配置环境变量 (可选)

在 `.env` 文件中:

```env
# 默认模板 (modern/classic/minimal) - 适用于所有文档类型
EXPORT_DEFAULT_TEMPLATE=modern
```

---

### 步骤 5: 验证安装

#### Python 测试

```python
# 在 backend 目录下启动 Python
.venv/Scripts/python.exe  # Windows
source .venv/bin/activate && python  # macOS/Linux

# 测试导入
>>> from app.modules.resumes.export import DocumentExportService, PDFGenerator
>>> DocumentExportService.get_available_document_types()
['resume']  # 未来会包含 'cover_letter' 等

>>> DocumentExportService.get_available_templates("resume")
['classic', 'minimal', 'modern']

>>> PDFGenerator.get_available_document_types()
['resume']
```

#### API 测试

启动后端:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

测试端点:

```bash
# 获取可用模板
curl http://localhost:8000/api/v1/resumes/templates
# 返回: ["classic", "minimal", "modern"]
```

---

## 使用方法

### API 端点

#### 1. 导出简历为 PDF

```http
POST /api/v1/resumes/{resume_id}/export
Authorization: Bearer {token}
Content-Type: application/json

{
  "template": "modern",        // 可选,默认使用配置中的模板
  "font_size": 12,            // 基础字号 (10-16)
  "include_metadata": false   // 是否包含生成时间
}
```

**响应:**
- 返回 PDF 文件 (二进制流)
- Header: `Content-Disposition: attachment; filename="..."`
- Header: `X-Template-Used: modern`

#### 2. 获取可用模板列表

```http
GET /api/v1/resumes/templates
```

**响应:**
```json
["classic", "minimal", "modern"]
```

### 编程方式使用

```python
from app.modules.resumes.export import PDFGenerator

# 初始化生成器
generator = PDFGenerator(
    template_name="modern",
    font_size=12,
    include_metadata=True
)

# 生成 PDF
pdf_bytes = generator.generate(
    markdown_content="# My Resume\n\n**Experience:** ...",
    title="Software Engineer Resume"
)

# 保存到文件
with open("resume.pdf", "wb") as f:
    f.write(pdf_bytes)
```

---

## 添加新模板

### 步骤 1: 创建 HTML 模板

创建 `export/templates/your_template.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
</head>
<body>
    <div class="resume-container your-template">
        <header class="resume-header">
            <h1 class="resume-title">{{ title }}</h1>
        </header>
        <main class="resume-content">
            {{ content|safe }}
        </main>
        {% if include_metadata %}
        <footer class="resume-footer">
            <p>Generated on {{ generated_at }}</p>
        </footer>
        {% endif %}
    </div>
</body>
</html>
```

### 步骤 2: 创建 CSS 样式

创建 `static/css/your_template.css`:

```css
.your-template {
    /* 自定义样式 */
}

.your-template .resume-title {
    font-size: 2em;
    color: #000;
}

/* 覆盖 base.css 中的样式 */
```

### 步骤 3: 自动生效

模板会自动被发现,无需修改代码。通过 API 测试:

```bash
POST /api/v1/resumes/{id}/export
{
  "template": "your_template"
}
```

---

## 配置说明

### 环境变量

在 `.env` 中配置:

```env
RESUME_EXPORT_DEFAULT_TEMPLATE=modern
```

### 代码配置

在 `backend/app/core/config.py` 中:

```python
class Settings(BaseSettings):
    RESUME_EXPORT_DEFAULT_TEMPLATE: str = "modern"
```

### 模板发现机制

- 扫描 `export/templates/` 目录
- 查找所有 `.html` 文件
- 排除 `base.html`
- 自动注册为可用模板

---

## 故障排除

### Q1: Windows 上出现 "OSError: cannot load library 'gobject-2.0-0'"

**原因:** GTK3 runtime 未安装或未添加到 PATH

**解决:**
1. 重新安装 GTK3 runtime
2. 确保选择 "Add to PATH"
3. 重启终端/IDE

### Q2: 中文显示为方块或乱码

**原因:** 字体文件缺失或路径错误

**解决:**
1. 检查 `app/modules/resumes/static/fonts/*.ttf` 是否存在
2. 确认文件名正确 (区分大小写)
3. 确保格式为 `.ttf` (不是 `.woff` 或 `.woff2`)

### Q3: "TemplateNotFound: modern.html"

**原因:** 模板文件缺失

**解决:**
1. 检查 `app/modules/resumes/export/templates/modern.html`
2. 确保所有模板文件已创建

### Q4: "ValueError: Invalid template"

**原因:** 模板验证失败

**解决:**
1. 使用可用模板 (通过 `/templates` 端点查询)
2. 检查 `RESUME_EXPORT_DEFAULT_TEMPLATE` 配置
3. 确保模板 `.html` 文件存在

### Q5: PDF 生成很慢 (首次 2-3 秒)

**原因:** weasyprint 首次加载字体较慢

**优化:**
- 后续生成会更快 (~0.5-1 秒)
- 考虑使用 Redis 缓存 PDF
- 使用后台任务异步生成

---

## 性能优化

### 1. 首次渲染

- **耗时:** 2-3 秒 (字体加载)
- **后续:** 0.5-1 秒
- **建议:** 添加 PDF 缓存

### 2. 内存占用

- **单次生成:** ~50-100MB
- **原因:** weasyprint 加载字体到内存
- **建议:** 监控内存使用,必要时限流

### 3. 并发处理

- **线程安全:** ✅ 是
- **每个请求:** 独立的生成器实例
- **建议:** 可以安全地并发处理多个请求

### 未来优化方向

- [ ] Redis 缓存生成的 PDF
- [ ] 后台任务队列 (Celery)
- [ ] S3/CDN 存储
- [ ] 字体预加载
- [ ] 批量导出

---

## 项目文件检查清单

```
backend/
├── app/
│   ├── core/
│   │   └── config.py                # ✅ RESUME_EXPORT_DEFAULT_TEMPLATE
│   └── modules/
│       └── resumes/
│           ├── export/
│           │   ├── __init__.py      # ✅
│           │   ├── generator.py     # ✅ PDFGenerator
│           │   ├── renderer.py      # ✅ MarkdownRenderer
│           │   └── templates/
│           │       ├── modern.html  # ✅
│           │       ├── classic.html # ✅
│           │       └── minimal.html # ✅
│           ├── static/
│           │   ├── css/
│           │   │   ├── base.css     # ✅
│           │   │   ├── modern.css   # ✅
│           │   │   ├── classic.css  # ✅
│           │   │   └── minimal.css  # ✅
│           │   └── fonts/
│           │       ├── NotoSansSC-Regular.ttf  # ⚠️ 需手动下载
│           │       ├── NotoSansSC-Bold.ttf     # ⚠️ 需手动下载
│           │       └── NotoSerifSC-Regular.ttf # ⚠️ 需手动下载
│           ├── schemas.py           # ✅ ResumeExportRequest/Response
│           ├── service.py           # ✅ export_resume_to_pdf()
│           └── router.py            # ✅ /export 和 /templates 端点
└── pyproject.toml                   # ✅ weasyprint, markdown2, jinja2
```

---

## 参考资料

### 官方文档

- [weasyprint Documentation](https://doc.courtbouillon.org/weasyprint/)
- [CSS Paged Media Module](https://www.w3.org/TR/css-page-3/)
- [markdown2 GitHub](https://github.com/trentm/python-markdown2)
- [Jinja2 Templates](https://jinja.palletsprojects.com/)
- [Noto Fonts](https://fonts.google.com/noto)

### 扩展阅读

- [CSS Print Layouts](https://www.smashingmagazine.com/2015/01/designing-for-print-with-css/)
- [PDF Generation Best Practices](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)

---

**最后更新:** 2025-01-24
