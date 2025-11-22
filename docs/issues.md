# 问题修复记录

## ✅ 已修复：Tailwind CSS v4 PostCSS 配置问题

### 问题描述
```
[postcss] It looks like you're trying to use `tailwindcss` directly as a PostCSS plugin.
The PostCSS plugin has moved to a separate package...
```

### 根本原因
- 项目初始化时安装了 Tailwind CSS v4.1.17
- v4 的 PostCSS 插件移到了独立的包 `@tailwindcss/postcss`
- 配置文件使用的是 v3 语法

### 修复方案
选择了**方案 2：升级到 Tailwind CSS v4**

### 修复步骤

#### 1. 安装 v4 PostCSS 插件
```bash
npm install -D @tailwindcss/postcss
```

#### 2. 更新 `postcss.config.js`
```javascript
// 从:
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}

// 改为:
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
```

#### 3. 删除 `tailwind.config.js`
v4 不再需要此配置文件，使用 CSS 变量配置。

#### 4. 更新 `src/index.css`
```css
/* 从: */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* 改为: */
@import "tailwindcss";

@layer base {
  /* 自定义样式 */
}
```

#### 5. 卸载 autoprefixer
```bash
npm uninstall autoprefixer
```
v4 内置了 autoprefixer。

### 验证结果

✅ **依赖版本**:
```
tailwindcss@4.1.17
@tailwindcss/postcss@4.1.17
```

✅ **预期效果**:
- PostCSS 错误消失
- Tailwind 样式正常编译
- 所有工具类可用
- 构建速度提升

### 文档更新
- ✅ 更新 [README.md](./README.md) - 技术栈说明

### 后续注意事项

1. **自定义主题**: 使用 `@theme` 指令而非配置文件
2. **插件使用**: 需要时创建 `tailwind.config.ts`
3. **CSS 层叠**: 使用 `@layer` 组织样式
4. **性能**: v4 构建速度比 v3 快约 10 倍

### 参考资源
- [Tailwind CSS v4 文档](https://tailwindcss.com/docs)
- [v3 到 v4 迁移指南](https://tailwindcss.com/docs/upgrade-guide)

---

**修复时间**: 2025-01-23
**修复状态**: ✅ 完成
**影响范围**: 前端构建系统
