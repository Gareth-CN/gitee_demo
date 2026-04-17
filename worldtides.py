import requests
import pandas as pd
import time
import re
from datetime import datetime, timezone

# =========================
# 参数设置
# =========================

apiKey = "94b0be98-af8d-42d6-bbbb-89ae034cb56e"

lat = 30.44968
lon = 122.27295

datum = "MSL"
step = 3600  # 秒（3600=逐小时）

tStart = datetime(2017,1,1,tzinfo=timezone.utc)
tEnd   = datetime(2019,1,1,tzinfo=timezone.utc)

pauseBetweenCalls = 1.2
maxRetry = 3

baseURL = "https://www.worldtides.info/api/v3"

# =========================
# 工具函数
# =========================

def month_start(dt):
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)

def next_month(dt):
    if dt.month == 12:
        return datetime(dt.year+1,1,1,tzinfo=timezone.utc)
    return datetime(dt.year,dt.month+1,1,tzinfo=timezone.utc)

def posix(dt):
    return int(dt.timestamp())

def parse_date(s):

    s = re.sub(r"Z$","+00:00",s)
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)

    try:
        return datetime.fromisoformat(s)
    except:
        return None

# =========================
# 下载
# =========================

allT = []
allH = []

tA = month_start(tStart)
seg = 0

while tA < tEnd:

    tB = min(next_month(tA),tEnd)

    seg += 1

    startUnix = posix(tA)
    lengthSec = int((tB-tA).total_seconds())

    url = (
        f"{baseURL}?heights"
        f"&lat={lat}"
        f"&lon={lon}"
        f"&start={startUnix}"
        f"&length={lengthSec}"
        f"&step={step}"
        f"&datum={datum}"
        f"&key={apiKey}"
    )

    print(f"[{seg:03d}] {tA} -> {tB}",end=" ")

    ok=False
    retry=0

    while not ok and retry<=maxRetry:

        try:

            r=requests.get(url,timeout=60)
            r.raise_for_status()

            S=r.json()

            ok=True
            print("OK",end=" ")

        except Exception as e:

            retry+=1
            print("retry",retry,end=" ")

            if retry>maxRetry:
                raise e

            time.sleep(2*retry)

    heights=S.get("heights")

    if not heights:
        raise Exception("no heights field")

    for h in heights:

        t=parse_date(h["date"])

        if t is None:
            continue

        allT.append(t)
        allH.append(h["height"])

    print(len(heights),"records")

    time.sleep(pauseBetweenCalls)

    tA=tB

# =========================
# 输出CSV
# =========================

df=pd.DataFrame({
    "time_utc":allT,
    "tide_m":allH
})

df=df.drop_duplicates(subset=["time_utc"]).sort_values("time_utc")

df["time_utc"]=df["time_utc"].dt.strftime("%Y-%m-%d %H:%M:%S")

outCsv=f"WorldTides_{tStart:%Y%m%d}_{tEnd:%Y%m%d}_{lat:.5f}_{lon:.5f}.csv"

df.to_csv(outCsv,index=False)

print("完成:",outCsv)
print("总记录:",len(df))