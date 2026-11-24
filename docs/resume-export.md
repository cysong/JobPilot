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
│   │   │   ├── base.css     # 版面规则: 页面、字体栈、间距、分页
│   │   │   ├── modern.css   # 只管颜色、字号、装饰
│   │   │   ├── classic.css
│   │   │   └── minimal.css
│   │   └── cover_letter/    # 求职信样式
│   │       ├── base.css
│   │       └── modern.css
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
    fonts-liberation2 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
```

`fonts-liberation2` 和 `fonts-noto-cjk` 是 PDF 用的字体, 见下一步。

---

### 步骤 3: 字体与样式约定

#### 字体

PDF 只用系统字体, 不再用 `@font-face` 加载仓库里的字体文件。字体由 Docker 镜像安装:

| 用途 | 字体 | Debian 包 |
|---|---|---|
| 英文无衬线 (modern / minimal) | Liberation Sans (与 Arial 同宽) | `fonts-liberation2` |
| 英文衬线 (classic / cover letter) | Liberation Serif (与 Times 同宽) | `fonts-liberation2` |
| 中文 | Noto Sans CJK SC / Noto Serif CJK SC | `fonts-noto-cjk` |

CSS 的 font-family 先写 Liberation, 再写 Noto CJK; 中文字符会按字形自动回退到 Noto CJK。
后面的 Arial、PingFang SC、Microsoft YaHei 等只是让 macOS / Windows 本地预览接近线上效果。

镜像里缺这些字体时, WeasyPrint 会回退到 DejaVu: 字形明显更宽 (页数变多), 且没有中文字形。

**检查容器里的字体:**

```bash
docker exec jobpilot-api fc-match "Liberation Sans"
docker exec jobpilot-api fc-match "Noto Sans CJK SC"
```

#### 字号

- 所有 CSS 尺寸都用相对单位 (em/rem)。
- `PDFGenerator` 把根字号 `html { font-size: Npt }` 作为最后一个样式表注入, 整个版面随之缩放。
- 请求不传 `font_size` 时按文档类型取默认值: 简历和 cover letter 都是 11pt (`PDFGenerator.DEFAULT_FONT_SIZES`)。

#### 样式分工

- `resume/base.css` 定义版面规则: 页面尺寸和边距 (1.5cm / 1.8cm)、字体栈、行高 1.4、统一的间距、分页规则。
- 分页规则: 标题 `break-after: avoid`, 正文 `orphans` / `widows` 为 2。要点 `li` 不加 `break-inside: avoid`, 否则带子列表的要点会被整块挤到下一页。
- 模板样式 (`modern.css` 等) 只改颜色、字号和装饰, 不改间距, 保证三个模板的版面一致。

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
  "font_size": 11,            // 可选, 基础字号 (10-16); 不传时为 11
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
    document_type="resume",
    template_name="modern",
    include_metadata=True,  # font_size omitted: 11pt
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

**原因:** 运行环境没有安装中文字体 (WeasyPrint 回退到没有中文字形的字体)

**解决:**
1. 确认镜像安装了 `fonts-noto-cjk` (见 Dockerfile)
2. 在容器里运行 `fc-match "Noto Sans CJK SC"`, 应输出 NotoSansCJK
3. 本机直接运行时, 安装任一中文字体 (macOS 自带 PingFang SC)

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
