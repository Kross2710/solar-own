import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Point to base directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from providers.base import VN_TZ
from server import store, history_provider, config

async def _fill_sample_gaps() -> int:
    """Lấp lỗ thủng `samples` (hôm qua + hôm nay) bằng đường cong 5 phút của SEMS.

    Mất điện/reboot/deploy -> không có mẫu phút nào trong lúc host tắt, nhưng `daily`
    vẫn đúng nhờ backfill => biểu đồ trong ngày lệch với con số tổng. Chạy sau mỗi
    lần backfill (khởi động + mỗi 12h) nên lỗ được vá trong ~15s sau khi bật lại.
    Chỉ 2 ngày gần nhất: ngày cũ hơn rồi cũng bị `prune(30d)` dọn, không đáng gọi API.
    """
    if not hasattr(history_provider, "fetch_day_curve"):
        return 0
    today = datetime.now(VN_TZ).date()
    total = 0
    for d in ((today - timedelta(days=1)).isoformat(), today.isoformat()):
        try:
            cur = await history_provider.fetch_day_curve(d) # type: ignore
            total += store.backfill_samples(d, cur.get("points") or [])
        except Exception as e:
            print(f"  [samples] lỗi lấp {d}: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(0.8)  # né rate-limit GY0429
    return total

async def backfill_loop():
    """Nền: kéo SẢN LƯỢNG NGÀY lịch sử từ SEMS về bảng `daily`."""
    if not hasattr(history_provider, "fetch_daily_history"):
        print("  [backfill] Provider không hỗ trợ fetch_daily_history. Dừng task.")
        return

    months_full = int(config.get("backfill_months", 18))
    # Chờ khởi tạo kết nối
    await asyncio.sleep(5)
    
    first = True
    while True:
        try:
            months = months_full if first else 2
            rows = await history_provider.fetch_daily_history(months=months) # type: ignore
            store.backfill_daily(rows)

            erows = {}
            if hasattr(history_provider, "fetch_daily_energy"):
                erows = await history_provider.fetch_daily_energy(months=months) # type: ignore
                store.backfill_energy(erows)

            scope = "đầy đủ" if first else "gần đây"
            print(
                f"  [backfill] đồng bộ {len(rows)} ngày sản lượng + {len(erows)} ngày "
                f"tiêu thụ/mua từ SEMS ({scope}); tổng {store.daily_count()} ngày",
                flush=True
            )
            first = False
        except Exception as e:
            print(f"  [backfill] lỗi: {type(e).__name__}: {e}", flush=True)
            
        # Vá đường cong phút cho khoảng host tắt (cúp điện/reboot/deploy)
        try:
            n = await _fill_sample_gaps()
            if n:
                print(f"  [samples] lấp {n} mẫu phút còn thiếu từ SEMS", flush=True)
        except Exception as e:
            print(f"  [samples] lỗi: {type(e).__name__}: {e}", flush=True)
        # Tính "điện nắng bị bỏ phí" cho các ngày gần đây (lấp ngày thiếu + cập nhật 2 ngày mới nhất)
        # if hasattr(history_provider, "fetch_day_curve"):
        #     try:
        #         have = store.curtailment_days()
        #         today = datetime.now(VN_TZ).date()
        #         yest = (today - timedelta(days=1)).isoformat()
        #         days = [r["day"] for r in store.daily(30)]
        #         todo = [d for d in days if d not in have or d >= yest]
        #         n = 0
        #         for d in todo:
        #             try:
        #                 est = await _curtail_for(d)
        #                 store.record_curtailment(d, est.get("lost_kwh") or 0, est.get("full_at"))
        #                 n += 1
        #             except Exception:
        #                 pass
        #             await asyncio.sleep(0.8)  # né rate-limit
        #         if n:
        #             print(f"  [curtailment] cập nhật {n} ngày", flush=True)
        #     except Exception as e:
        #         print(f"  [curtailment] lỗi: {type(e).__name__}: {e}", flush=True)

        # BẮT BUỘC phải có sleep để tránh spam server SEMS (chạy lại mỗi 12 giờ)
        await asyncio.sleep(12 * 3600)

async def main():
    try:
        await backfill_loop()
    finally:
        # Đóng kết nối an toàn nếu có method close
        if hasattr(history_provider, "close"):
            await history_provider.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  [backfill] Đã dừng task.")