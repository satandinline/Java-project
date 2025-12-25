#!/bin/bash
# 全功能测试脚本
# 使用方法：bash test_all_features.sh

echo "=========================================="
echo "开始测试所有新功能"
echo "=========================================="

BASE_URL="http://localhost:7200"
USER_ID=1  # 请根据实际情况修改

echo ""
echo "1. 测试全文检索（不限制返回条数）"
echo "----------------------------------------"
curl -X GET "${BASE_URL}/api/search?q=春节" | jq '.data | length'
echo ""

echo "2. 测试图文互搜（三列布局）"
echo "----------------------------------------"
curl -X POST "${BASE_URL}/api/multimodal/search" \
  -H "X-User-Id: ${USER_ID}" \
  -F "mode=text" \
  -F "query=春节" \
  -F "user_id=${USER_ID}" | jq '.vector_results, .text_results, .image_results | length'
echo ""

echo "3. 测试AI自动标注（需要等待10秒后检查annotation_records表）"
echo "----------------------------------------"
echo "注意：自动标注服务在后台运行，每10秒检查一次新增资源"
echo "请手动检查数据库annotation_records表是否有新记录"
echo ""

echo "4. 测试AIGC文字生成（检查retrieval_id字段）"
echo "----------------------------------------"
SESSION_RESPONSE=$(curl -X POST "${BASE_URL}/api/aigc/sessions" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: ${USER_ID}" \
  -d '{"summary": "测试会话", "mode": "text"}')
SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.session.id')
echo "会话ID: ${SESSION_ID}"

curl -X POST "${BASE_URL}/api/aigc/ask" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: ${USER_ID}" \
  -d "{
    \"query\": \"请介绍一下春节的习俗\",
    \"session_id\": ${SESSION_ID},
    \"mode\": \"text\"
  }" | jq '.retrieved_resources'

echo ""
echo "检查qa_messages表的retrieval_id字段："
echo "SELECT retrieval_id FROM qa_messages WHERE session_id = ${SESSION_ID} ORDER BY id DESC LIMIT 1;"
echo ""

echo "5. 测试评论点赞通知"
echo "----------------------------------------"
COMMENT_RESPONSE=$(curl -X POST "${BASE_URL}/api/comments" \
  -H "Content-Type: application/json" \
  -d "{
    \"resource_id\": 1,
    \"user_id\": ${USER_ID},
    \"comment_content\": \"测试评论\"
  }")
COMMENT_ID=$(echo $COMMENT_RESPONSE | jq -r '.comment.id')
echo "评论ID: ${COMMENT_ID}"

# 使用另一个用户点赞（需要先创建另一个用户）
LIKE_USER_ID=2
curl -X POST "${BASE_URL}/api/comments/${COMMENT_ID}/like" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": ${LIKE_USER_ID}}"

echo ""
echo "检查通知："
curl -X GET "${BASE_URL}/api/notifications?user_id=${USER_ID}" | jq '.notifications[] | select(.notification_type == "like")'
echo ""

echo "6. 测试评论回复通知"
echo "----------------------------------------"
curl -X POST "${BASE_URL}/api/comments/${COMMENT_ID}/reply" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": ${LIKE_USER_ID},
    \"reply_content\": \"测试回复\"
  }"

echo ""
echo "检查通知："
curl -X GET "${BASE_URL}/api/notifications?user_id=${USER_ID}" | jq '.notifications[] | select(.notification_type == "reply")'
echo ""

echo "7. 测试标记全部已读"
echo "----------------------------------------"
curl -X POST "${BASE_URL}/api/notifications/mark-all-read" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: ${USER_ID}"

echo ""
echo "检查未读通知数量："
curl -X GET "${BASE_URL}/api/notifications?user_id=${USER_ID}&is_read=0" | jq '.notifications | length'
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="

