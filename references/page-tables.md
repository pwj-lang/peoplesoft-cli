# PeopleSoft Page 相关表结构参考

> 2026-07-17 从 PANWX25 实测获取。23 张 PSPNL* 表，以下为 Page 定义核心 5 张。

## 表全景

| 表 | 字段数 | 索引数 | 级别 | 说明 |
|----|--------|--------|------|------|
| PSPNLDEFN | 30 | 4 | Page 定义 | Page 元数据 |
| PSPNLFIELD | 98 | 11 | Page 控件 | 每个控件的 Record 绑定、类型、位置、标签 |
| PSPNLFIELDEXT | 31 | 1 | 控件扩展 | PT/Fluid 扩展属性 |
| PSPNLGROUP | 8 | 4 | Component 映射 | PNLGRPNAME → PNLNAME 对应 |
| PSPNLGRPDEFN | 43 | 3 | Component 定义 | 组件属性 |

其余 18 张：PSPNLDEFNLANG, PSPNLFIELDLANG, PSPNLGDEFNLANG, PSPNLGROUPLANG, PSPNLHTMLLANG, PSPNLBTNLANG, PSPNLCTLDATALNG (多语言), PSPNLACEGRDAXIS/DATA (Analytic Grid), PSPNLACTIVEX, PSPNLBTNDATA, PSPNLCNTRLDATA, PSPNLDEL, PSPNLGRPDEL, PSPNLGRPSCRIPTS, PSPNLHTMLAREA, PSPNLTREECTRL。

---

## PSPNLDEFN — Page 定义

Key: PNLNAME

| 字段 | 类型 | 说明 |
|------|------|------|
| PNLNAME | char(30) | Page 名称（主键） |
| VERSION | number(10) | 版本号 |
| PNLTYPE | number(1) | 页面类型码 |
| FIELDCOUNT | number(4) | 字段个数 |
| MAXPNLFLDID | number(4) | 最大字段 ID |
| GRIDHORZ / GRIDVERT | number(4) | 网格间距 |
| HELPCONTEXTNUM | number(10) | 帮助上下文编号 |
| PANELTOP/LEFT/RIGHT/BOTTOM | number(4) | 面板坐标 |
| PNLSTYLE | char(30) | 样式 (PromptTableEdit) |
| STYLESHEETNAME | char(30) | 经典样式表名 |
| FFSTYLESHEETNAME | char(30) | Fluid 样式表 |
| FFSTYLEDESKTOP/PHONE/TABLET/MEDIUM/EXLARGE | char(100) | 各设备 Fluid 样式 |
| PNLUSE | number(5) | 页面用途位掩码 |
| PNLUSETEMP | number(5) | 用途模板 |
| DEFERPROC | number(1) | 延迟处理 |
| DESCR | char(30) | 短描述 |
| DESCRLONG | CLOB | 长描述 |
| POPUPMENU | char(30) | 弹出菜单 |
| LICENSE_CODE | char(64) | 许可证代码 |
| LASTUPDDTTM | datetime | 最后更新 |
| LASTUPDOPRID | char(30) | 更新人 |
| OBJECTOWNERID | char(4) | 对象所有者 |

### 重要发现

- **PNLGRPNAME 不在此表中** — 它在 PSPNLGROUP（Component 映射表）。
- **PNLUSE（不是 PNLUSAGE）** 是 number(5) 位掩码，PNLTYPE 才 number(1) 只存类型码。
- **PNLLBLTEXTSRC 不在此表中** — 可能在其他表。
- **PNLCLASS 不在此表中** — 对应的是 PNLSTYLE + STYLESHEETNAME + FFSTYLE* 系列。
- **PNLSTYLE / STYLESHEETNAME / FFSTYLE\*** 的具体取值和作用待查。

---

## PSPNLFIELD — Page 控件

Key: PNLNAME + PNLFLDID

### 核心字段（GetPageStruct v1 选用）

| 字段 | 类型 | 分类 | 说明 |
|------|------|------|------|
| PNLFLDID | number(4) | 主键 | 字段 ID（Page 内唯一） |
| RECNAME | char(15) | 绑定 | 所属 Record |
| FIELDNAME | char(18) | 绑定 | 字段名 |
| FIELDTYPE | number(2) | 类型 | 控件类型码 |
| FIELDUSE | number(10) | 属性 | 用途位掩码 |
| OCCURSLEVEL | number(1) | 层级 | 出现级别 (0/1/2/3) |
| FIELDLEFT/TOP/RIGHT/BOTTOM | number(4) | 位置 | 控件四角坐标 |
| EDITSIZE | number(5) | 尺寸 | 编辑框尺寸 |
| LBLTEXT | char(60) | 标签 | 标签文本 |
| LBLTYPE | number(1) | 标签 | 标签类型 |
| LBLLOC | number(1) | 标签 | 标签位置 |

### FIELDTYPE 码表（2026-09-06 struct v2 语料实证，部分确认）

| 码 | 推测类型 | 证据/条数 |
|----|----------|-----------|
| 4 | Edit Box | 25996 条，FIELDNAME 全是真实字段名 |
| 5 | Drop-Down List | 3003 条，如 HR_STATUS、ACTION |
| 7 | Check Box | 1728 条，如 ACTIVE、FLG、OVERRIDE |
| 12 | Push Button/Hyperlink | 2764 条，如 LINK_PB、DONE_PB、*_BTN |
| 6 | Long Edit Box | 713 条，如 NOTE、CON_NOTE |
| 8 | Radio Button | 549 条 |
| 0 | Static Text | 1093 条 |
| 11 | scrollArea / **subPage** | 2261 条 | 2026-09-06 实证：SUBPNLNAME 非空=subPage 嵌入（FMLA_LV_ACTIVITY/JOB_DATA3） |
| 27 | **scrollArea（滚动框）** | 1005 条 | 2026-09-06 实证修正（AAP_TBL #7 + PSPNLCNTRLDATA 关联）；旧"Horizontal Rule"证伪 |
| 19 | **grid** | 1259 条 | 2026-09-06 实证修正（GRDCOLUMNCOUNT>0）；旧"Scroll Area 变体"证伪 |
| 2 | Group Box | 6944 条 | |
| 10 | 分隔线 | 187 条 | |
| 23 | 分隔线 | 865 条 | |
| 25 | **htmlArea** | 22 条 | 2026-09-06 实证（PSPNLHTMLAREA 关联行）；旧猜测 13 证伪 |
| 13 | hyperlink | — | 2026-09-06 实证（PBDISPLAYTYPE 区分样式） |

**FIELDUSE 位掩码（2026-09-06 实证更新）**：与 PSRECFIELD.USEEDIT 不同。已实证：bit0(1)=required、bit1(2)=invisible/hrule基值、bit2(4)=displayOnly、bit19(524288)=button/hyperlink 类、bit12(4096)=grid/scroll 类、bit26(67108864)=groupBox 基值。其余位待查。

**PNLFLDID 分配规则（2026-09-06 实证）**：新控件 PNLFLDID = MAXPNLFLDID + 1，单调递增；删除产生的空洞不复用（ABBR_TYPE 从 2 起、JPM_JP_GROUPS 25 控件 maxid=53）。写后需联动 FIELDCOUNT/MAXPNLFLDID/VERSION。

**关键列实证值**：editBox/dropDown DSPLFORMAT=2097160、checkBox=524288、staticText=1、groupBox=524289；LBLTYPE 1=字面量/2=checkbox右侧/3=RFT标签/7=消息目录；checkbox ONVALUE/OFFVALUE 默认 Y/N；几乎所有控件 DEFERPROC=1、OCCURSCOUNT1-3=1、OCCURSOFFSET1-3=20；PSDBFIELD 无 LABEL_ID 列，字段默认 RFT 标签 ID=字段名。

---

## PSPNLFIELDEXT — 控件扩展

Key: PNLNAME + PNLFLDID（同 PSPNLFIELD）

PT/Fluid 扩展属性：PTMODALHEIGHT/WIDTH, PTPOPUPPNL, GRPBOXTYPE, PLACEHOLDER, SCROLLBARS, MINNUMBER/MAXNUMBER/STEPNUMBER, PARENTPNLFLDID, PAGEPNLFLDID, FIELDUSETEMP2, FFSTYLELONG (CLOB) 等 31 字段。

---

## PSPNLGROUP — Component → Page 映射

Key: PNLGRPNAME + MARKET + PNLNAME

| 字段 | 类型 | 说明 |
|------|------|------|
| PNLGRPNAME | char(18) | Component 名（主键） |
| MARKET | char(3) | 市场（主键） |
| PNLNAME | char(30) | Page 名（主键） |
| SUBITEMNUM | number(4) | 子项序号 |
| ITEMNAME | char(30) | 项名 |
| ITEMLABEL | char(30) | 项标签 |
| FOLDERTABLABEL | char(18) | 文件夹/标签 |
| HIDDEN | number(2) | 隐藏标志 |

### 重要：PNLGRPNAME 的真正位置

PNLGRPNAME 在 PSPNLGROUP 中，是 **Component → Page 的多对多映射**，不是 Page 自身的属性。PSPNLFIELD.GOTOPNLGRPNAME 是页面控件的导航目标。

---

## PSPNLGRPDEFN — Component 定义

Key: PNLGRPNAME + MARKET

43 字段，核心：SEARCHRECNAME, ADDSRCHRECNAME, SEARCHPNLNAME, ACTIONS, FLUIDMODE, LAYOUTMODE, PNLGRPUSE, DESCR/DESCRLONG, DISABLESAVE, FORCESEARCH 等。

---

## 已知缺口

- [x] FIELDTYPE 常用码已实证（0/2/4/5/7/12/13/19/23）；罕见码未穷举
- [x] FIELDUSE 常用位已实证（见上）；高位组合未穷举
- [ ] PNLUSE 位掩码含义未解码
- [ ] PNLSTYLE / STYLESHEETNAME 取值含义未确认
