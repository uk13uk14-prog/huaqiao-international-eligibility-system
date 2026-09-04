# 7-day Pro Trial (V1)

新用户注册自动获得 **7 天 Pro 完整体验**；到期后数据保留，权限回落到 Free（含现有「非核心院校」免费可见策略）。

## 实现要点

| 项 | 说明 |
|----|------|
| Schema migration | **不需要** — 复用 `users.plan_code` + `users.membership_until` |
| Trial plan code | `pro_trial` |
| Trial 时长 | `TRIAL_DAYS=7`（服务端 `utcnow`） |
| Trial ACTIVE | `is_paid=True` → 与当前 Pro 相同 entitlement |
| Trial EXPIRED | `is_paid=False` → Free limits（`university_limit=8` + `is_core=False` → 现网约 3 所） |
| 老用户 | 不自动改写；`free` 保持 free；`vip_*` + `membership_until=NULL` 视为在期保护 |

## 关键文件

- `app/services/membership_trial.py`
- `app/services/security.py` / `permissions.py` / `student_profile_entitlements.py`
- `app/main.py` register + entitlements payload
- H5: `huaqiao-app` trial badge + 注册入口

## 测试

```bash
cd huaqiao-saas-pro/backend
pytest tests/test_pro_trial.py tests/test_student_profile_slots.py -q
```

## 部署

**不要直接改 M1 production branch。** 合并/验收后再择机发布；本功能上线后**仅新注册**走 Trial。
