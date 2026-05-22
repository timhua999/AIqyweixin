# 百运（by56.com）查价接口调用说明

> **用途**：本文档为百运 Router API 交接说明（§3.1 查价 / §3.6 轨迹 / §3.7 跟踪号）。代码见 `adapters/by56_client.py`（公共参数与签名）、`adapters/by56.py`（业务解析）、`orchestrator/quote_flow.py` / `track_flow.py`（企微 LLM 抽参）。
>
> 开放平台入口：https://www.by56.com/openPlatform  
> 合作方案：**客户 API 接入**（查价/下单）

| 项 | 内容 |
|----|------|
| 文档版本 | 1.0 |
| 维护人 | zxb |
| 最后更新 | 2026-05-20 |

---

## 1. 环境与账号

| 项 | 值 |
|----|-----|
| 测试环境 Base URL | 【https://unsbapi.by56.com/router/api】
| 生产环境 Base URL | 【https://unapi.by56.com/router/api】
| 应用标识 AppId / ClientId | 【待填写】 |
| 应用密钥 AppSecret / ClientSecret | 【待填写】（仅配置在 `.env`，勿提交 Git） |
| IP 白名单 | 【待填写】有/无，若有列出服务器公网 IP |
| 开通的运输方式 | 【快递】快递 / 专线 / 空运 / 小包 / FBA / 海运… |

本项目环境变量（与 `.env.example` 一致）：

| 环境变量 | 说明 |
|----------|------|
| `BY56_ENABLED` | `true` 时注册百运适配器 |
| `BY56_BASE_URL` | 接口根地址（测试/生产二选一） |
| `BY56_BYKEY` | 分配的 ByKey（与 `BY56_APP_ID` 二选一，代码优先 BYKEY） |
| `BY56_APP_SECRET` | 签名密钥（参与签名时转大写） |
| `BY56_CALLS` | 调用来源，默认 `byapi` |
| `BY56_METHOD_QUOTE` | §3.1 快递查价，默认 `...GetCommodityEXP` |
| `BY56_METHOD_TRACK_BATCH` | §3.6 货物追踪，默认 `...QueryBatch` |
| `BY56_METHOD_DELIVERY_NO` | §3.7 获取跟踪号，默认 `...GetDeliveryNO` |
| `BY56_METHOD_COMMODITY` | 与 `BY56_METHOD_QUOTE` 同 method（兼容旧配置） |
| `BY56_TIMEOUT_SECONDS` | HTTP 超时，默认 30 |
| `WECOM_QUOTE_MAX_OFFERS` | 企微查价回复展示渠道条数，默认 3 |

---

## 2. 鉴权方式（已定稿：TOP Router + form 表单）

- [x] **单 URL POST**：`BY56_BASE_URL` = 测试/生产完整地址（见 §1）
- [x] **Content-Type**：`application/x-www-form-urlencoded`
- [x] **公共参数在 Body**：见 §3.1；业务参数与公共参数同级
- [x] **签名**：`sign_method=md5`，算法见 §2.1

### 2.1 签名算法和调用示例【这是by56的签名代码，C#编写】
 using System;
    using System.Collections.Generic;
    using System.Linq;
    using System.Text;
    using System.Net;
    using System.IO;
    using System.Text.RegularExpressions;
    using System.Security.Cryptography;

namespace WinUI
{
    public class testAdaptation
    {
        /// <summary>
        /// 给TOP请求签名 API v2.0
        /// </summary>
        /// <param name="parameters">所有字符型的TOP请求参数</param>
        /// <param name="secret">签名密钥</param>
        /// <returns>签名</returns>
        protected static string CreateSign(IDictionary<string, string> parameters, string secret)
        {
            parameters.Remove("sign");
            IDictionary<string, string> sortedParams = new SortedDictionary<string, string>(parameters);
            IEnumerator<KeyValuePair<string, string>> dem = sortedParams.GetEnumerator();
            StringBuilder query = new StringBuilder(secret);
            while (dem.MoveNext())
            {
                string key = dem.Current.Key;
                string value = dem.Current.Value;
                if (!string.IsNullOrEmpty(key) && !string.IsNullOrEmpty(value))
                {
                    query.Append(key).Append(value);
                }
            }
            query.Append(secret);

            MD5 md5 = MD5.Create();
            byte[] bytes = md5.ComputeHash(Encoding.UTF8.GetBytes(query.ToString()));
            StringBuilder result = new StringBuilder();
            for (int i = 0; i < bytes.Length; i++)
            {
                string hex = bytes[i].ToString("X");
                if (hex.Length == 1)
                {
                    result.Append("0");
                }
                result.Append(hex);
            }
            return result.ToString();
        }


        /// <summary>
        /// 组装普通文本请求参数。
        /// </summary>
        /// <param name="parameters">Key-Value形式请求参数字典</param>
        /// <returns>URL编码后的请求数据</returns>
        protected static string PostData(IDictionary<string, string> parameters)
        {
            StringBuilder postData = new StringBuilder();
            bool hasParam = false;
            IEnumerator<KeyValuePair<string, string>> dem = parameters.GetEnumerator();
            while (dem.MoveNext())
            {
                string name = dem.Current.Key;
                string value = dem.Current.Value;
                // 忽略参数名或参数值为空的参数
                if (!string.IsNullOrEmpty(name))//&& !string.IsNullOrEmpty(value)
                {
                    if (hasParam)
                    {
                        postData.Append("&");
                    }

                    postData.Append(name);
                    postData.Append("=");
                    postData.Append(Uri.EscapeDataString(value));
                    hasParam = true;
                }
            }
            return postData.ToString();
        }

        /// <summary>
        /// TOP API POST 请求
        /// </summary>
        /// <param name="url">请求容器URL</param>
        /// <param name="appkey">AppKey</param>
        /// <param name="appSecret">AppSecret</param>
        /// <param name="method">API接口方法名</param>
        /// <param name="calls">调用来源</param>
        /// <param name="param">请求参数</param>
        /// <returns>返回字符串</returns>
        public static string Post(string url, string appkey, string appSecret, string method, string calls, IDictionary<string, string> param)
        {
            #region -----API系统参数----
            param.Add("bykey", appkey.ToUpper());
            param.Add("method", method);
            //param.Add("session", session);
            param.Add("timestamp", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            param.Add("calls", calls);
            param.Add("format", "json");
            //param.Add("v", "2.0");
            param.Add("sign_method", "md5");
            param.Add("sign", CreateSign(param, appSecret.ToUpper()));
            #endregion

            string result = string.Empty;

            #region ---- 完成 HTTP POST 请求----
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
            req.Method = "POST";
            req.KeepAlive = true;
            req.Timeout = 300000;
            req.ContentType = "application/x-www-form-urlencoded";//;charset=utf-8
            byte[] postData = Encoding.UTF8.GetBytes(PostData(param));
            Stream reqStream = req.GetRequestStream();
            reqStream.Write(postData, 0, postData.Length);
            reqStream.Close();
            HttpWebResponse rsp = (HttpWebResponse)req.GetResponse();
            Encoding encoding = Encoding.GetEncoding(rsp.CharacterSet);
            Stream stream = null;
            StreamReader reader = null;
            stream = rsp.GetResponseStream();
            reader = new StreamReader(stream, encoding);
            result = reader.ReadToEnd();
            if (reader != null) reader.Close();
            if (stream != null) stream.Close();
            if (rsp != null) rsp.Close();
            #endregion

            return Regex.Replace(result, @"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "");

        }
    }
}
C#调用方法事例：
IDictionary<string, string> param = new Dictionary<string, string>();
param.Add("id", "1");

testAdaptation.Post("https://unsbapi.by56.com/router/api", 
"FD981D0B-BC8B-4A55-ABD0-C571B51B4990",
"028D0512-E130-4EB3-8583-BE7F53FF7085", 
"By56CustomerAPI.byExpOrder.ExpOrder.GetCommodityEXP","byapi", param); 


```
1. 去掉 sign；其余参数 key、value 均非空才参与
2. 按 key 字典序排序
3. 拼接：secret + key1 + value1 + key2 + value2 + ... + secret（secret 使用大写）
4. sign = MD5(UTF8(拼接串))，十六进制大写
5. bykey 传参时使用 ToUpper()
```
实现：`src/aiqyweixin/adapters/by56_client.py` → `create_sign()`

**与百运下发的 `CallInterface.py` 一致（生产必按此实现）：**

1. 参与签名的参数：**排除 `sign`**，且 key、value 均非空  
2. 排序：按参数名 **不区分大小写**（`sorted(keys, key=str.lower)`）  
3. 拼接：`secret.upper() + key1 + value1 + ... + secret.upper()`  
4. `MD5(UTF8)` → 十六进制 **大写**  
5. POST 时：`bykey` 转大写；`method` 转 **全大写**（与 Python 示例一致）  
6. `timestamp` 格式：`yyyy-MM-dd HH:mm:ss`（空格，**不要用 ISO 的 `T`**）

**凭证对应关系（勿填反）：**

| C# `Post(url, appkey, appSecret, ...)` | 环境变量 | 表单字段 |
|----------------------------------------|----------|----------|
| 第 2 参数 appkey | `BY56_BYKEY` | `bykey` |
| 第 3 参数 appSecret | `BY56_APP_SECRET` | 仅参与签名，不进表单 |

### 2.2 获取 Token（若适用）【待填写】

| 项 | 值 |
|----|-----|
| Token 接口路径 | 【待填写】 |
| 请求方式 | GET / POST |
| 有效期 | 【待填写】秒 |
| 刷新方式 | 【待填写】 |

---

## 3. 接口说明（对应 [open.by56 接口详细](https://open.by56.com/apicus/#/common/preface)）

| 项 | 值 |
|----|-----|
| 调用方式 | 所有业务共用一个 URL，通过 `method` 区分 |
| HTTP 方法 | POST |
| Content-Type | `application/x-www-form-urlencoded` |

### 3.1 公共请求参数（每个 method 必填）

> 代码：`By56RouterClient._system_params()`
bykey
类型：String
是否必填：是
说明：分配的 ByKey。

method
类型：String
是否必填：是
说明：需要连接接口的名称。

timestamp
类型：String
是否必填：是
说明：时间戳，格式为 yyyy-MM-dd HH:mm:ss，时区为 GMT+8，例如：2016-01-01 12:00:00。API 服务端允许客户端请求最大时间误差为 10 分钟。

calls
类型：String
是否必填：是
说明：调用来源 如：byerp,byapp,Byapi,bysup。

format
类型：String
是否必填：是
说明：响应格式。默认为 json (暂时只支持 json 格式)。

sign
类型：String
是否必填：是
说明：API 输入参数签名结果，签名算法参照下面的介绍。

sign_method
类型：String
是否必填：是
说明：固定传 `md5`。

```http
POST https://unsbapi.by56.com/router/api
Content-Type: application/x-www-form-urlencoded

bykey=FD981D0B-...&method=BY56CUSTOMERAPI.BYEXPORDER.EXPORDER.GETCOMMODITYEXP&timestamp=2026-05-20+12:00:00&calls=byapi&format=json&sign_method=md5&sign=...&StartCityKey=深圳市&CountryKey=US&Weight=10&Volume=0&SpecialItems=139&PackgeType=1
```

### 3.2 公共返回参数（每个 method）

> 代码：`By56RouterClient.parse_result()` — **成功：`ResultCode == 0`**
字段代码：ResultCode
字段名称：操作状态代码
数据类型：整数
是否必填：是
备注：请求操作执行状态
状态说明：
0. 请求操作处理成功
身份验证失败
系统繁忙
数据验证失败，缺少必须的请求参数或请求参数值无效
字段代码：Message
字段名称：操作状态描述
数据类型：文本
是否必填：否
备注：对操作结果的补充说明，操作成功时为空
字段代码：Data
字段名称：返回结果
数据类型：集合 / 对象 / 具体值
是否必填：否
备注：请求操作的实际响应结果，根据具体功能定义不同，仅 ResultCode=0 时返回，详见各功能响应说明

```json
{
  "ResultCode": 0,
  "Message": "",
  "Data": { }
}
```

### 3.3 业务接口一览

| 章节 | method | 功能 | 主要入参 | 代码入口 |
|------|--------|------|----------|----------|
| §3.1 | `...GetCommodityEXP` | 快递查价 | StartCityKey, CountryKey, Weight, Volume, SpecialItems, PackgeType | `quote()` / `quote_flow` |
| §3.6 | `...QueryBatch` | 货物追踪（轨迹） | TrackNo（≤5 个） | `query_track_batch()` / `track_flow` |
| §3.7 | `...GetDeliveryNO` | 获取跟踪号 | WaybillNO, WaybillType | `get_delivery_no()` / `track_flow` |

### 3.1 快递查价（GetCommodityEXP）

| 项 | 值 |
|----|-----|
| 接口名称 | 快递查价 |
| method | `By56CustomerAPI.byExpOrder.ExpOrder.GetCommodityEXP` |
| 环境变量 | `BY56_METHOD_QUOTE`（或与 `BY56_METHOD_COMMODITY` 相同） |
| 代码 | `By56Adapter.quote()` / `quote_service.query_quote()` |
| 企微 | `orchestrator/quote_flow.py`（LLM 抽参 → 查价） |

#### 3.1.1 业务请求参数

| BY56 字段 | 类型 | 必填 | 说明 |
|-----------|------|------|------|
| `StartCityKey` | String [20] | Y | 起运城市，默认「深圳市」 |
| `CountryKey` | String [2] | Y | 目的国家 **二字码**（如 US、GB），非中文国名 |
| `Weight` | Decimal(10,3) | Y | 重量 (kg) |
| `Volume` | Decimal(10,3) | Y | 体积，无则传 `0` |
| `SpecialItems` | String [50] | Y | 货物种类 ID，多个用英文逗号分隔，见下表 |
| `PackgeType` | Int32 | Y | 包裹类型：`1`=WPX，`2`=DOC，`3`=PAK |
| `ModeCode` | String [50] | N | 运输方式 |
| `ChannelNames` | String [500] | N | 渠道名称，多个英文逗号分隔 |
| `ChannelCodes` | String [500] | N | 渠道编码，多个英文逗号分隔；非空时优先于名称 |
| `QueryType` | Int32 | N | 查价模式：`1`=总货物信息(默认)，`2`=详细货物信息 |
| `Quanlity` | Int32 | N | 总件数（文档拼写为 Quanlity），默认 1 |
| `GoodInfos` | String | N | 详细材积 JSON 数组字符串（`QueryType=2` 时用） |

**SpecialItems 常用枚举（代码 `BY56_SPECIAL_ITEMS` / `list_commodities()`）：**

| ID | 名称 |
|----|------|
| 139 | 普货 |
| 108 | 内置电池 |
| 109 | 配套电池 |
| 111 | 移动电源 |
| 103 | 纯电池 |
| 110 | 手机 (无电) |
| 204 | 手机 (内电) |
| 205 | 手机 (配电) |
| 105 | 电子烟 |
| 203 | 电容 |
| 106 | 纺织品 |
| 107 | 木箱 |
| 296 | 食品 |
| 308 | 防疫物资 |
| 320 | 电子产品 |

#### 3.1.2 内部 DTO → BY56 映射

| 内部字段 `QuoteRequest` | BY56 字段 | 说明 |
|-------------------------|-----------|------|
| `origin_city` | `StartCityKey` | 默认深圳市 |
| `destination_country` | `CountryKey` | 须 2 位国家码 |
| `weight_kg` | `Weight` | |
| `volume_cbm` | `Volume` | 默认 0 |
| `goods_type` / `extra` | `SpecialItems` | 中文名映射为 ID |
| `pieces` | `Quanlity` | |
| `transport_mode` | `ModeCode` | |
| `extra.PackgeType` | `PackgeType` | 默认 1 |

#### 3.1.3 响应 Data[]（渠道报价列表）

`ResultCode=0` 时 `Data` 为 **数组**，每项字段如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Channel` | String [32] | Y | 渠道 ID（GUID） |
| `ChannelName` | String [50] | Y | 渠道名称 |
| `ModeCode` | String [50] | Y | 运输方式 |
| `StartCityName` | String [50] | Y | 起运地名称 |
| `CountryName` | String [50] | Y | 目的地名称 |
| `CountryNameEn` | String | N | 目的地英文名 |
| `ChannelDescription` | String [200] | N | 渠道描述（企微全量展示） |
| `RiskWarning` | String [200] | N | 风险提示（企微全量展示） |
| `SpecialItems` | String [100] | Y | 可接货物描述 |
| `Period` | String [50] | N | 时效（如 `5` 表示天数） |
| `CharWeight` | Decimal(10,3) | Y | 计费重 |
| `Price` | Decimal(10,3) | Y | 单价 |
| `TotalPrice` | Decimal(10,3) | Y | 总费用（展示主价格） |
| `FeeTotal` | Decimal(10,3) | Y | 附加费总额（文档偶有 `FeeToal` 笔误） |
| `TrafficAmount` | Decimal(10,3) | Y | 运费总额（人民币） |
| `TrafficFuelAmount` | Decimal(10,3) | Y | 运费燃油附加费 |
| `FeeList` | List | N | 附加费明细，见下表 |
| `IsTax` | Bool | Y | 是否含税 |
| `ChannelTypeCode` | Int | N | 账号类别 1~6 |
| `ServiceTypeName` | String | N | 服务类别名称 |
| `BusinessType` | Int | N | 1 快递 / 2 国际专线 / 3 专线小包 |
| `ServiceName` | String | N | 服务集合（逗号分隔） |
| `ServiceNameList` | List | N | 服务名称数组 |
| `SupplierCode` | String | N | 供应商编码 |

**FeeList[] 元素：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `FeeName` | String [50] | Y | 附加费名称 |
| `FeePrice` | Decimal(10,3) | Y | 金额（人民币） |

**响应示例（节选）：**

```json
{
  "ResultCode": 0,
  "Message": "",
  "Data": [{
    "ChannelName": "H-59 HKDHL代理价(美洲）",
    "ModeCode": "DHL-HK",
    "StartCityName": "深圳市",
    "CountryName": "美国",
    "Period": "5",
    "CharWeight": 10.0,
    "Price": 66.18,
    "TotalPrice": 661.76,
    "FeeTotal": 0.0,
    "RiskWarning": "...",
    "ChannelDescription": "...",
    "FeeList": []
  }]
}
```

代码：`QuoteOffer` / `_parse_quote_row()`；企微 `QuoteResult.to_markdown()`。

**联调：**

```bash
python scripts/test_by56_quote.py --dest-country US --origin-city 深圳市 --weight-kg 10 --volume 0 --goods-type 普货
python scripts/test_by56_quote.py --list-commodity   # 输出 SpecialItems 枚举表
```

---

### 3.6 货物追踪（QueryBatch）

| 项 | 值 |
|----|-----|
| 接口名称 | 货物追踪（物流轨迹节点） |
| method | `By56CustomerAPI.byPackOrder.PackOrder.QueryBatch` |
| 环境变量 | `BY56_METHOD_TRACK_BATCH` |
| 代码 | `By56Adapter.query_track_batch()` / `track_service.query_track_batch()` |
| 企微 | `orchestrator/track_flow.py`，意图 `track`（**不是** §3.7） |

> **注意**：用户说「**跟踪号**」应走 §3.7；「**轨迹** / 到哪了 / 上网状态」走本节。

#### 3.6.1 业务请求参数

| BY56 字段 | 类型 | 必填 | 说明 |
|-----------|------|------|------|
| `TrackNo` | String [50] | Y | 订单号、代理单号或跟踪号；**单次最多 5 个**，英文逗号分隔；仅支持快递业务 |

#### 3.6.2 响应 Data[]

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `WaybillNo` | String [100] | Y | 订单号 |
| `TrackStatus` | String [50] | Y | 上网状态（如「已上网」「未上网」） |
| `GoodsTrackLst` | List | — | 轨迹节点列表，见下表 |

**GoodsTrackLst[]（GoodsTrack）：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `WaybillNo` | String | — | 订单号 |
| `TrackTime` | DateTime | — | 轨迹时间，`yyyy-MM-dd HH:mm:ss` |
| `Position` | String | — | 地点 |
| `TrackInfo` | String | — | 轨迹描述 |

**响应示例：**

```json
{
  "ResultCode": 0,
  "Message": "",
  "Data": [{
    "WaybillNo": "WE01709009681",
    "TrackStatus": "已上网",
    "GoodsTrackLst": [{
      "WaybillNo": "WE01709009681",
      "TrackTime": "2017-09-25 21:20:54",
      "Position": "Scraper",
      "TrackInfo": ""
    }]
  }]
}
```

代码：`TrackShipment` / `GoodsTrackEvent` / `TrackBatchResult.to_markdown()`。

**联调：**

```bash
python scripts/test_by56_track_batch.py WE01709009681
python scripts/test_by56_track_batch.py NO1 NO2 NO3   # 最多 5 个
```

---

### 3.7 获取百运跟踪号（GetDeliveryNO）

| 项 | 值 |
|----|-----|
| method | `By56CustomerAPI.byPackOrder.PackOrder.GetDeliveryNO` |
| 环境变量 | `BY56_METHOD_DELIVERY_NO` |
| 代码 | `By56Adapter.get_delivery_no()` / `track_service.query_delivery_no()` |

**业务请求参数**（[open.by56 接口详细 §3.7](https://open.by56.com/apicus/#/common/preface)）：

| BY56 字段 | 类型 | 必填 | 说明 |
|-----------|------|------|------|
| `WaybillNO` | string | Y | 订单号；**多个单号用英文逗号 `,` 拼接** |
| `WaybillType` | int | Y | 业务类型：`1` = 快递和专线；`20` = FBA |

**响应示例（`ResultCode=0`）：**

```json
{
  "ResultCode": 0,
  "Message": "",
  "Data": [
    {
      "WaybillNO": "WE01711001841",
      "IsDeliveryNO": true,
      "DeliveryNO": "7419577196",
      "ModeCode": "",
      "BaseModeCode": ""
    }
  ]
}
```

**Data[] 字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `WaybillNO` | string | 订单号 |
| `IsDeliveryNO` | bool | 是否有跟踪号 |
| `DeliveryNO` | string | 跟踪号（`IsDeliveryNO=false` 时可能为空） |
| `ModeCode` | string | 运输方式子类 |
| `BaseModeCode` | string | 运输方式大类 |

代码：`DeliveryNoItem` / `_parse_delivery_row()` in `by56.py`。

**联调：**

```bash
python scripts/test_by56_delivery_no.py ORDER001 ORDER002 --waybill-type 1
python scripts/test_by56_delivery_no.py FBAORDER001 --waybill-type 20
```

企微话术与意图（`track_flow.py`）：

| 用户意图 | intent | 接口 |
|----------|--------|------|
| 查轨迹、物流节点、到哪了 | `track` | §3.6 |
| 查跟踪号、查询跟踪号 | `delivery_no` | §3.7 |

---

## 4. 企微机器人对接说明

| 能力 | 条件 | 模块 |
|------|------|------|
| 询价 | `LLM_ENABLED` + `BY56_ENABLED` + 凭证正确 | `quote_flow` → §3.1 |
| 轨迹 | 同上 | `track_flow` → §3.6 |
| 跟踪号 | 同上 | `track_flow` → §3.7 |
| 其它对话 | `LLM_ENABLED` | `orchestrator/chat.py` 通用 LLM |

回调入口：`POST /wecom/callback` → `build_wecom_reply()`，处理顺序：**轨迹/跟踪号 → 询价 → 通用 LLM**。

---

## 5. 响应与 DTO 映射汇总

| 接口 | Data 形态 | Python DTO | 企微展示 |
|------|-----------|------------|----------|
| §3.1 查价 | `Data[]` 渠道 | `QuoteResult` / `QuoteOffer` | `to_markdown()`，默认前 N 条 |
| §3.6 轨迹 | `Data[]` 运单 | `TrackBatchResult` / `TrackShipment` | 全量轨迹节点 |
| §3.7 跟踪号 | `Data[]` | `DeliveryNoResult` / `DeliveryNoItem` | 订单号 ↔ 跟踪号 |

**成功码**：`ResultCode == 0`（`By56RouterClient.parse_result()`）

---

## 6. 错误码 【待填写】

| code | 含义 | 处理建议 |
|------|------|----------|
| 0 | 成功 | 解析 `data` |
| 【待填写】 | 【待填写】 | 提示用户 / 重试 / 转人工 |

---

## 7. 业务规则 【待填写】

- 计费重：实重与体积重取大？体积重公式？**【待填写】**
- 是否支持批量查价：**【待填写】**
- QPS / 日调用上限：**【待填写】**
- 同一请求幂等键：**【待填写】**

---

## 8. 内部实现映射（与代码同步）

| 模块 | 路径 |
|------|------|
| Router 客户端 / 签名 | `src/aiqyweixin/adapters/by56_client.py` |
| 业务适配 / 解析 | `src/aiqyweixin/adapters/by56.py` |
| 注册 | `src/aiqyweixin/adapters/registry.py` |
| 询价服务 | `src/aiqyweixin/services/quote_service.py` |
| 轨迹/跟踪号服务 | `src/aiqyweixin/services/track_service.py` |
| DTO | `src/aiqyweixin/models/dto.py` |
| 企微询价编排 | `src/aiqyweixin/orchestrator/quote_flow.py` |
| 企微轨迹编排 | `src/aiqyweixin/orchestrator/track_flow.py` |
| 企微回复入口 | `src/aiqyweixin/orchestrator/chat.py` |
| 官方 Python 样例 | 项目根目录 `CallInterface.py`（签名对照） |

| 联调脚本 | 接口 |
|----------|------|
| `scripts/test_by56_quote.py` | §3.1 |
| `scripts/test_by56_track_batch.py` | §3.6 |
| `scripts/test_by56_delivery_no.py` | §3.7 |
| `scripts/test_by56_quote.py --test-sign` | 签名校验 |

---

## 9. 本地联调

```bash
# .env：BY56_ENABLED=true、BY56_BYKEY、BY56_APP_SECRET、BY56_BASE_URL

# §3.1 查价
python scripts/test_by56_quote.py --dest-country US --origin-city 深圳市 --weight-kg 10 --volume 0 --goods-type 普货

# §3.6 轨迹
python scripts/test_by56_track_batch.py WE01709009681

# §3.7 跟踪号
python scripts/test_by56_delivery_no.py WE01711001841 --waybill-type 1

# 签名（与 CallInterface.py 对照）
python scripts/test_by56_quote.py --test-sign
```

---

## 10. 修订记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-05-20 | 1.0 | 补全 §3.1/§3.6/§3.7 字段；纠正 §3.6=QueryBatch 轨迹、§3.7=GetDeliveryNO；签名与企微编排 |
| — | 0.1 | 初稿模板 |
