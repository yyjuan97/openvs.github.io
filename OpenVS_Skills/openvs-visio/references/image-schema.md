# 图片分析 JSON Schema

Agent 看图后按本 schema 产出 JSON，保存为 .json 文件交给 `scripts/render_image.py` 渲染。

## 坐标系（最关键，必须严格遵守）

- 原点 (0, 0) 在图片**左上角**，**x 向右增大、y 向下增大**，所有坐标范围 0.0~1.0
- `x, y` 是形状的**左上角**坐标（不是中心点！）；`width, height` 是形状宽高
- 归一化基准是**整张图片**（含留白），直接按像素换算最准确：

```
x      = 形状左边缘像素 / 图片总宽像素
y      = 形状上边缘像素 / 图片总高像素
width  = 形状宽度像素   / 图片总宽像素
height = 形状高度像素   / 图片总高像素
```

- 连接线的 `start_x/start_y/end_x/end_y` 同样是左上角原点的归一化坐标，取线在形状边缘附近的端点。渲染器会自动把端点吸附到形状边缘，给**近似值**即可，不必精确到像素

## 顶层字段：image_aspect（必填）

```json
"image_aspect": 1.78
```

值 = 图片宽像素 / 图片高像素（如 1920/1080 = 1.78）。渲染器据此自动选页面方向，**防止纵向图被横向画布拉扁**：

| image_aspect | 页面 |
|---|---|
| ≥ 1.15（横图） | 11" × 8.5" 横向 |
| ≤ 0.87（纵图） | 8.5" × 11" 纵向 |
| 之间（近正方） | 10" × 10" |

## 只填看得清的，看不清的整项省略

- **文字、形状、连接关系**：必填，逐个识别，不遗漏可见元素
- **颜色类**（fill_color / border_color / text_color / line_color / background_color / floating_texts.color）：只有颜色明确、非默认白底黑框时才填；白底、拿不准、颜色很淡的一律**省略**——渲染器自动用透明填充+黑色边框。**禁止猜颜色**
- **font_size / font_bold / border_width / border_style / rotation / text_alignment**：全部可选。**font_size 一律省略**，渲染器按形状高度自动算字号（不同 Agent 目测 pt 是最大差异源之一）；只有标题等明显特大文字可用 `font_bold: true` 强调
- 形状内文字换行用 `\n`；无文字填 `""`

## 输出结构

```json
{
  "image_aspect": 1.78,
  "diagram_type": "flowchart|architecture|relationship|org_chart|mind_map|network|other",
  "title": "图表标题（没有可省略）",
  "shapes": [
    {
      "id": 1,
      "type": "rectangle",
      "x": 0.10, "y": 0.08,
      "width": 0.16, "height": 0.09,
      "text": "开始",
      "font_bold": true
    }
  ],
  "connections": [
    {
      "from_shape_id": 1,
      "to_shape_id": 2,
      "type": "straight",
      "label": "是",
      "has_arrow": true,
      "start_x": 0.18, "start_y": 0.17,
      "end_x": 0.18, "end_y": 0.28
    }
  ],
  "floating_texts": [
    {
      "text": "注：数据每日同步",
      "x": 0.05, "y": 0.90,
      "width": 0.30, "height": 0.05,
      "font_bold": false
    }
  ]
}
```

## 字段速查

### shapes（必填，至少 1 个）

| 字段 | 必填 | 说明 |
|---|---|---|
| id | 是 | 唯一整数 |
| type | 是 | `rectangle` / `rounded_rectangle`（圆角，常用于起止）/ `diamond`（判断）/ `ellipse` / `parallelogram`（数据）/ `document` / `storage`（磁盘/数据库）/ `hexagon` / `textbox`（无边框无填充文字块） |
| x, y, width, height | 是 | 左上角归一化坐标+尺寸（数字，非字符串） |
| text | 是 | 形状文字，无则 `""` |
| fill_color / border_color / text_color | 否 | `#RRGGBB`；看不清就省略 |
| border_width / border_style | 否 | border_style：`solid`/`dashed`/`dotted` |
| font_size | 否 | **建议省略**，省略时自动估算；手动覆盖时范围约 8~24 |
| font_bold / text_alignment / rotation | 否 | text_alignment：`left`/`center`/`right` |

### connections（可选）

- 必填：`from_shape_id`、`to_shape_id`（必须存在于 shapes）、`type`（`straight`/`elbow`/`curved`）、`start_x/start_y/end_x/end_y`
- 可选：`label`、`line_color`、`line_width`、`line_style`、`has_arrow`
- 只画**实际可见**的线；形状对齐不算连接；沿箭头方向定 from/to；同一对形状不要正反两条重复线
- 容器（分组框）和子形状都要画，但线连到**子形状**而非容器

### floating_texts（可选）

不属于任何形状的独立文字（图例、注释）。`text`、`x/y/width/height` 必填；颜色字号看不清就省略。

## 完整计算示例（横图 1920×1080）

假设一个"开始"圆角框，左边缘 x=192px、上边缘 y=86px、宽 307px、高 97px：

```
image_aspect = 1920 / 1080 = 1.78
x      = 192 / 1920 = 0.10
y      = 86  / 1080 = 0.08
width  = 307 / 1920 = 0.16
height = 97  / 1080 = 0.09
```

对应 JSON：

```json
{
  "image_aspect": 1.78,
  "shapes": [
    {"id": 1, "type": "rounded_rectangle", "x": 0.10, "y": 0.08,
     "width": 0.16, "height": 0.09, "text": "开始", "font_bold": true}
  ],
  "connections": []
}
```

## JSON 有效性

- 只有一个 JSON 对象；括号引号配对；键名双引号；无尾逗号
- 字符串内的 `"` 和 `\` 转义
- 所有坐标是数字（`0.1` 而非 `"0.1"`），且形状不要超出 0~1 范围
