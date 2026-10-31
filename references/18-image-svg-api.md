# SVG Image 定义

`image struct/exists/clone` 复用 Content 原生管理器及 HTML Read/Write Service Operation，使用 `kind=image`、CONTTYPE=1 和独立 `image1:` 原始版本。仅开放本模块实际使用的单一 SVG Image 的原生克隆；不宣称支持 PNG/JPEG、本地文件导入、多个替代图或多语言编辑。这与全局 Image Field 不同。

先读取源 SVG 与不存在的目标名称。原生 Content 管理器对 Image 返回空的 `ContStrData`，该属性不代表图片正文；读取返回基准及翻译 BLOB 指纹。clone 同时携带源与目标的原始快照，通过原生完整对象 SaveNewDefn 保留二进制数据；缺失428、冲突409。支持原生保存后回滚的 dry-run，必须另读目标及源证明无变更；真实保存后回读并核对原生 BLOB。工程类型49，完整值为名称/1。HTML 与 SVG 共用已有操作权限，不创建新授权。

```powershell
python scripts/peoplesoft_api.py image struct C_REFRESH --output source-image.json
python scripts/peoplesoft_api.py image struct C_XI_REFRESH --output target-absent.json
python scripts/peoplesoft_api.py image clone C_XI_REFRESH --source C_REFRESH --source-snapshot source-image.json --snapshot target-absent.json --project C_XI_261031 --dry-run
python scripts/peoplesoft_api.py image clone C_XI_REFRESH --source C_REFRESH --source-snapshot source-image.json --snapshot target-absent.json --project C_XI_261031
```

需要同步部署 `CoreOperHtmlDefn`、`NativeAdapter` 和 CLI。权限错误须处理实际授权；不回退通用 SQL 写入。
