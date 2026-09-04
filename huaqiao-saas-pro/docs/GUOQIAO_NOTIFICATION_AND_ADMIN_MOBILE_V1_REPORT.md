# GUOQIAO Notification Center + Admin Mobile V1 — Status Report

**Branch:** `cursor/notification-admin-mobile-v1-eee9`  
**PR:** https://github.com/uk13uk14-prog/huaqiao-international-eligibility-system/pull/11  
**Base:** `cursor/mobile-cloud-preview`  
**Updated:** 2026-09-04

| 项 | 结果 |
| --- | --- |
| NOTIFICATION_CENTER | **PASS**（统一模型 + API） |
| STUDENT_NOTIFICATION_CENTER | **PASS**（H5 🔔 + 分类页） |
| ADMIN_NOTIFICATION_CENTER | **PASS**（移动端「通知」Tab） |
| REMINDER_RULE_ENGINE | **PASS**（规则表 + 30/14/7/3/1/0） |
| TIMELINE_INTEGRATION | **PASS**（个性化 `StudentTimelineItem`） |
| PERSONALIZED_REMINDER | **PASS** |
| IN_APP_NOTIFICATION | **PASS** |
| HIGH_PRIORITY_POPUP | **PASS**（只弹一次） |
| CRITICAL_POPUP | **PASS**（读后才消失） |
| ADMIN_AI_REVIEW_NOTIFICATION | **PASS**（AI 草稿 → 运营待审） |
| STUDENT_PUBLISHED_REPORT_NOTIFICATION | **PASS**（发布 → 学生） |
| QUIET_HOURS | **PASS**（CRITICAL 可破静默） |
| DEDUPLICATION | **PASS** |
| PUSH_PROVIDER_ARCHITECTURE | **PASS**（IN_APP + FCM/APNS/WebPush stub） |
| WEB_PUSH_READY | **NO**（仅 abstraction，无正式凭证） |
| FCM_READY | **NO**（未编造 key） |
| APNS_READY | **NO** |
| ADMIN_MOBILE_LAYOUT | **PASS**（首页/学生/审核/**通知**/我的） |
| CAPACITOR_ADDED | **YES**（`com.guoqiao.admin`） |
| ANDROID_APK | **YES**（沿用既有 debug APK） |
| MIGRATION_008 | **PROMOTED**（`alembic/versions/008_notification_center_v1.py`） |
| STAGING_UPGRADE | **PASS**（真库 `huaqiao_admin_staging` @:5432） |
| STAGING_DOWNGRADE | **PASS** |
| STAGING_REUPGRADE | **PASS** |
| STAGING_HEAD | **008_notification_center_v1** |
| PRODUCTION_MIGRATION_APPLIED | **NO** |
| DATABASE_CHANGED | **NO**（生产） |
| PRODUCTION_CHANGED | **NO** |
| TUNNEL_CHANGED | **NO** |
| CADDY_CHANGED | **NO** |
| SECRET_CHANGED | **NO** |
| CNBER_CHANGED | **NO** |
| MAIN_CHANGED | **NO** |
| TESTS | **9 passed**（`test_notification_center_v1.py`） |
| PR_OPENED | **YES**（#11 draft） |
| READY_FOR_NEXT_PHASE | **YES**（待真机联调 + FCM/APNS 凭证） |
| NEXT_ACTION | 1) PR 评审合并 2) 真机联调 HIGH/CRITICAL 弹窗 3) 配置 FCM/APNS 后再开 Push 实发 4) 生产 008 另开 ops 窗口（需 backup） |

## Staging notes

- Script: `huaqiao-saas-pro/backend/scripts/staging_migrate_008.sh`
- Boolean defaults fixed to `sa.true()` for Postgres compatibility
- Pre-migrate backup: `/tmp/guoqiao-staging-backups/huaqiao_admin_staging_pre_008_*.dump`
- Production `:5433/huaqiao` untouched
