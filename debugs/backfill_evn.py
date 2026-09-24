import asyncio
from pathlib import Path
import sys

# Point to base directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from server import store, config

def build_evn_portal(cfg: dict):
    """Dựng EvnPortal từ config.evn.portal nếu BẬT + đủ creds; ngược lại None.

    Độc lập với `source` (SEMS): EVN CSKH là nguồn phụ ground-truth, bật/tắt riêng.
    """
    p = (cfg.get("evn") or {}).get("portal") or {}
    # Debug
    print(f"  [evn] portal config: {p}")
    if not p.get("enabled"):
        return None
    if not (p.get("customer_id") and p.get("username") and p.get("password")):
        return None
    from providers.evn_portal import EvnPortal
    return EvnPortal(
        customer_id=p["customer_id"],
        username=p["username"],
        password=p["password"],
        base_url=p.get("base_url", "https://cskh.evnhcmc.vn"),
        backfill_start_year=int(p.get("backfill_start_year", 2022)),
    )

evn_portal = build_evn_portal(config)
# print(f"  [evn] portal: {evn_portal.name if evn_portal else 'disabled'}")

async def evn_loop():
    """Nền: kéo số liệu THẬT từ cổng EVN CSKH (kWh/chỉ số ngày + hoá đơn kỳ).

    Độc lập poll/backfill SEMS. Lần đầu backfill từ start_year (mặc định 2022); sau đó
    đồng bộ cửa sổ ngắn mỗi 12h (EVN cập nhật ~6h/lần nên 12h là dư). Tắt nếu config
    không bật `evn.portal.enabled`.
    """
    if evn_portal is None:
        print("  [evn] EVN portal chưa bật hoặc thiếu thông tin đăng nhập trong config.")
        return
    
    await asyncio.sleep(5)  # nhường poll/backfill SEMS khởi động trước
    first = True
    while True:
        try:
            if first:
                r = await evn_portal.backfill(store) # type: ignore
                print(f"  [evn] backfill {r['days']} ngày + {r['bills']} kỳ hoá đơn; "
                      f"tổng {store.evn_counts()}", flush=True)
                first = False
            else:
                r = await evn_portal.sync_recent(store) # type: ignore
                print(f"  [evn] đồng bộ {r['days']} ngày gần đây + hoá đơn; "
                      f"tổng {store.evn_counts()}", flush=True)
        except Exception as e:
            print(f"  [evn] lỗi: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(12 * 3600)  # đồng bộ lại mỗi 12 giờ
        
async def main():
    try:
        await evn_loop()
    finally:
        # Đóng kết nối an toàn nếu có method close
        if hasattr(evn_portal, "close"):
            await evn_portal.close() # type: ignore

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  [evn] Đã dừng task.")