# 百运（by56.com）查价接口调用说明

> **用途**：本文档为「唯一事实来源」。请对照 [百运 open API 文档](https://open.by56.com/apicus/#/common/preface) 补全 **【待填写】** 项；代码见 `adapters/by56_client.py`（§3.1/3.2）、`adapters/by56.py`（§3.6/3.7）。
>
> 开放平台入口：https://www.by56.com/openPlatform  
> 合作方案：**客户 API 接入**（查价/下单）

| 项 | 内容 |
|----|------|
| 文档版本 | 0.1-草案 |
| 维护人 | 【zxb】 |
| 最后更新 | 【2026/05/20】 |

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
| `BY56_METHOD_COMMODITY` | §3.6 method，默认 `By56CustomerAPI.byPackOrder.PackOrder.QueryBatch` |
| `BY56_METHOD_QUOTE` | §3.7 method，默认 `By56CustomerAPI.byPackOrder.PackOrder.GetDeliveryNO` **【请按 open.by56 接口详细核对】** |
| `BY56_TIMEOUT_SECONDS` | HTTP 超时，默认 30 |

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

```http
POST https://unsbapi.by56.com/router/api
Content-Type: application/x-www-form-urlencoded

bykey=FD981D0B-...&method=By56CustomerAPI.byExpOrder.ExpOrder.QueryPriceEXP&timestamp=2026-05-20+12:00:00&calls=byapi&format=json&sign_method=md5&sign=...&StartCity=深圳&DestCountry=US&Weight=100
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

### 3.6 获取货物种类（GetCommodityEXP）

| 项 | 值 |
|----|-----|
| method（默认） | `By56CustomerAPI.byExpOrder.ExpOrder.GetCommodityEXP` |
| 环境变量 | `BY56_METHOD_COMMODITY` |
| 代码 | `By56Adapter.list_commodities()` / `get_commodity_exp()` |

**业务请求参数**（请按 open.by56 §3.6 补全）：

| BY56 字段 | 类型 | 必填 | 说明 |
|-----------|------|------|------|
| `id` | string | N | 示例 C# 调用传 `id=1` **【待确认含义】** |
| 【待填写】 | | | |

**响应 Data**：货物种类列表，用于映射 `CommodityID`（代码按名称模糊匹配「普货」等）。

### 3.7 快递查价（QueryPriceEXP）

| 项 | 值 |
|----|-----|
| method（默认，**请核对官方文档编号 3.7 的 method 全名**） | `By56CustomerAPI.byExpOrder.ExpOrder.QueryPriceEXP` |
| 环境变量 | `BY56_METHOD_QUOTE` |
| 代码 | `By56Adapter.quote()` → `query_price_exp()` |

**业务请求参数**（代码映射 `BY56_QUOTE_FIELD_MAP`，请按 §3.7 修正）：

| 内部字段 | BY56 字段（当前实现） | 必填 | 说明 |
|----------|----------------------|------|------|
| `origin_city` | `StartCity` | Y | 起运城市 **【待确认】** |
| `destination_country` | `DestCountry` | Y | 目的国 **【待确认】** |
| `destination_city` | `DestCity` | N | 目的城市 **【待确认】** |
| `weight_kg` | `Weight` | Y | 重量 kg **【待确认】** |
| `volume_cbm` | `Volume` | N | 体积 **【待确认】** |
| `pieces` | `Quantity` | N | 件数 **【待确认】** |
| `goods_type` / commodity_id | `CommodityID` | N | 可先 §3.6 解析 **【待确认】** |
| `origin_country` | `StartCountry` | N | **【待确认】** |

**响应 Data**：渠道/价格列表；解析字段见 `by56.py` 中 `_NAME_KEYS` / `_PRICE_KEYS` 等 **【待按 §3.7 响应表补全】**。

---

## 4. 请求参数表（汇总，与 §3.7 同步）

| 内部字段（DTO） | BY56 字段名 | 类型 | 必填 | 说明 / 枚举 |
|-----------------|-------------|------|------|-------------|
| `origin_country` | `originCountry` | string | Y | 起运国家，ISO 或中文，例 CN **【中文】** |
| `origin_city` | `originCity` | string | N | 起运城市 **【深圳市】** |
| `destination_country` | `destCountry` | string | Y | 目的国家 **【美国】** |
| `destination_city` | `destCity` | string | N | 目的城市 **【待确认】** |
| `weight_kg` | `weight` | number | Y | 重量 kg **【待确认】** |
| `volume_cbm` | `volume` | number | N | 体积 CBM **【待确认】** |
| `pieces` | `pieces` | int | Y | 件数 **【待确认】** |
| `goods_type` | `cargoType` | string | Y | 139 普货
108 内置电池
109 配套电池
111 移动电源
103 纯电池
110 手机(无电)
204 手机(内电)
205 手机(配电)
105 电子烟
203 电容
106 纺织品
107 木箱
296 食品
308 防疫物资
320 电子产品 **【通过中文传ID】** |
| `transport_mode` | `productType` | string | N | 快递/专线/空运… **【待确认】** |
| — | `bykey` / `method` / `timestamp` / `calls` / `format` / `sign` | | | §3.1 公共参数 |

---

## 5. 响应参数表（汇总）

| BY56 字段路径 | 内部字段（DTO） | 类型 | 说明 |
|---------------|-----------------|------|------|
| `ResultCode` | — | int | **0=成功** |
| `Message` | `error_message` | string | 失败说明 |
| `Data` | `offers[]` 来源 | object/array | §3.7 渠道列表 **【待确认路径】** |
| `channels[].channelName` | `offers[].channel_name` | string | 渠道名称 **【待确认】** |
| `channels[].totalPrice` | `offers[].total_price` | number | 总价（含税与否）**【待确认】** |
| `channels[].currency` | `offers[].currency` | string | 币种 **【待确认】** |
| `channels[].transitTime` | `offers[].transit_time` | string | 时效描述 **【待确认】** |
| `channels[].chargeWeight` | `offers[].charge_weight_kg` | number | 计费重 **【待确认】** |

**成功码取值**：`ResultCode == 0`

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

实现文件：

| 模块 | 路径 |
|------|------|
| 适配器 | `src/aiqyweixin/adapters/by56.py` |
| 注册 | `src/aiqyweixin/adapters/registry.py` |
| 询价服务 | `src/aiqyweixin/services/quote_service.py` |
| DTO | `src/aiqyweixin/models/dto.py` |
| 联调脚本 | `scripts/test_by56_quote.py` |

修改本文 **§3.6 / §3.7** 后，请同步修改：

- `adapters/by56_client.py`（签名、公共参数）
- `adapters/by56.py` 中 `BY56_QUOTE_FIELD_MAP`、`_NAME_KEYS` / `_PRICE_KEYS`
- `.env` 中 `BY56_METHOD_COMMODITY` / `BY56_METHOD_QUOTE`（与官方 method 全名一致）

---

## 9. 本地联调

```bash
# 配置 .env 中 BY56_* 后
# §3.6 货物种类
python scripts/test_by56_quote.py --list-commodity

# §3.7 查价
python scripts/test_by56_quote.py \
  --origin-country CN --origin-city 深圳 \
  --dest-country US --dest-city 洛杉矶 \
  --weight-kg 100 --goods-type 普货
```

---

## 10. 修订记录

| 日期 | 版本 | 说明 |
|------|------|------|
| 【待填写】 | 0.1 | 初稿模板 |
