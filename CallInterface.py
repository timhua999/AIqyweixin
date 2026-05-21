# coding:utf-8

import requests
import copy
import hashlib
import time

# MD5签名
def CreateSign(paraments,secret):
    sort1 = copy.deepcopy(paraments)
    for key, value in sort1.items():
        if key == "" or value == "":
            del sort1[key]
    sortedParam = sorted(sort1.items(), key=lambda d: d[0].lower())
    query = [secret.upper()]
    for i in range(len(sortedParam)):
        query.append(sortedParam[i][0])
        query.append(sortedParam[i][1])
    str = "".join(query)
    str1 = str + secret.upper()
    m = hashlib.md5()
    m.update(str1.encode("utf8"))
    result = m.hexdigest()
    return result.upper()

# 快递批量查价
def Query_Order_Batch(OrderID):
    '''
    快递批量查价
    :param strPara: 订单号/跟踪号集合
    '''

    url = "https://unapi.by56.com/router/api"
    by_key = "111"
    by_secret = "222"
    method = "By56CustomerAPI.byExpOrder.ExpOrder.QueryOrderBatch"  
    ttime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    post_data = {
        "strPara": "{'WaybillNOLst':['400004792','400004553']}",
        "bykey": by_key,
        "method": method.upper(),
        "timestamp": ttime,
        "calls": "by56Test",
        "format": "json",
        "sign_method": "md5",
    }

    post_data["sign"] = CreateSign(post_data,by_secret)
    response = requests.post(url, data=post_data)
    #print(post_data)

    print(response.text)

if __name__ == "__main__":
    Query_Order_Batch("WE02009007894")

