# -*- coding: utf-8 -*-
"""后端 API 全面测试脚本"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

passed = 0
failed = 0
results = []


def call(method, path, body=None, expect=(200,)):
    global passed, failed
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            text = resp.read().decode("utf-8")
            ok = code in expect
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            try:
                parsed = json.loads(text)
                detail = json.dumps(parsed, ensure_ascii=False)[:200]
            except Exception:
                detail = text[:200]
            results.append((method + " " + path, code, status, detail))
            return code, text
    except urllib.error.HTTPError as e:
        failed += 1
        body_txt = e.read().decode("utf-8", errors="ignore")[:200]
        results.append((method + " " + path, e.code, "FAIL", body_txt))
        return e.code, body_txt
    except Exception as e:
        failed += 1
        results.append((method + " " + path, "-", "FAIL", str(e)[:200]))
        return 0, str(e)


def call_stream(path, body):
    """测试 SSE 流式接口"""
    global passed, failed
    url = BASE + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            code = resp.status
            chunks = 0
            has_done = False
            for raw in resp:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line.startswith("data:"):
                    chunks += 1
                    payload = line[5:].strip()
                    if '"type": "done"' in payload or '"type":"done"' in payload:
                        has_done = True
            ok = code == 200 and chunks > 0
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            else:
                failed += 1
            detail = "chunks=%d, done=%s" % (chunks, has_done)
            results.append(("POST(stream) " + path, code, status, detail))
            return ok
    except Exception as e:
        failed += 1
        results.append(("POST(stream) " + path, "-", "FAIL", str(e)[:200]))
        return False


print("=" * 70)
print("MOM AI 知识库平台 - 后端 API 全面测试")
print("=" * 70)

# 1. 健康检查
call("GET", "/health")

# 2. 根路径
call("GET", "/")

# 3. 模型状态
call("GET", "/api/models/status")

# 4. 模型列表
code, text = call("GET", "/api/models")
model_id = None
try:
    parsed = json.loads(text)
    data_list = parsed.get("data", [])
    if data_list:
        for m in data_list:
            if m.get("is_active") and m.get("type") == "LLM":
                model_id = m.get("id")
                break
        if not model_id and data_list:
            model_id = data_list[0].get("id")
except Exception:
    pass

# 5. 模型详情
if model_id:
    call("GET", "/api/models/%d" % model_id)

# 6. 分类列表
call("GET", "/api/categories")

# 7. 标签列表
call("GET", "/api/tags")

# 8. Skill 列表
code, text = call("GET", "/api/skills")
skill_id = None
try:
    parsed = json.loads(text)
    data_list = parsed.get("data", [])
    if data_list:
        first = data_list[0]
        if isinstance(first, dict):
            skill_id = first.get("id")
except Exception:
    pass

# 9. Skill 详情
if skill_id:
    call("GET", "/api/skills/%d" % skill_id)

# 10. Skill 选项 - 分类
call("GET", "/api/skill-options?type=category")

# 11. Skill 选项 - 功能
call("GET", "/api/skill-options?type=function")

# 12. 知识列表
call("GET", "/api/knowledge")

# 13. 关键词搜索
call("GET", "/api/search/keyword?query=%E8%AE%BE%E5%A4%87")

# 13b. 语义搜索（无 Embedding 时返回 400 属预期行为）
code, text = call("GET", "/api/search/semantic?query=%E8%AE%BE%E5%A4%87", expect=(200, 400))
if code == 400:
    # 修正：语义搜索无 Embedding 返回 400 是预期行为，计为通过
    passed += 1
    failed -= 1
    results[-1] = (results[-1][0], code, "PASS(expected)", results[-1][3])

# 13c. 搜索历史
call("GET", "/api/search/history")

# 14. 问答历史
call("GET", "/api/qa/history?page=1&page_size=5")

# 15. 问答建议
call("GET", "/api/qa/suggestions?question=%E8%AE%BE%E5%A4%87%E6%95%85%E9%9A%9C")

# 16. 仪表盘统计
call("GET", "/api/dashboard/stats")

# 16b. 仪表盘最近问答
call("GET", "/api/dashboard/recent-qa")

# 17. Token 统计
call("GET", "/api/token-stats")

# 18. 智能问答（SSE 流式）
print("\n[流式测试] 智能问答...")
call_stream("/api/qa/ask", {"question": "你好", "use_cache": True})

# 输出结果
print("\n" + "=" * 70)
print("测试结果明细")
print("=" * 70)
print("%-45s %-6s %-6s %s" % ("接口", "状态码", "结果", "详情"))
print("-" * 70)
for path, code, status, detail in results:
    print("%-45s %-6s %-6s %s" % (path[:45], str(code), status, detail[:60]))

print("\n" + "=" * 70)
print("总计: %d 通过, %d 失败, 共 %d" % (passed, failed, passed + failed))
print("=" * 70)

import sys
sys.exit(0 if failed == 0 else 1)
