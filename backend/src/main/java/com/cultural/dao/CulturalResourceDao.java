package com.cultural.dao;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;

/**
 * 文化资源数据访问对象
 */
@Repository
public class CulturalResourceDao {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    /**
     * 获取首页资源列表（从crawled_images表）
     */
    public List<Map<String, Object>> getHomeResources(int page, int pageSize) {
        String sql = "SELECT id, file_name, storage_path, tags, dimensions, crawl_time, " +
                     "resource_id, entity_id, festival_name " +
                     "FROM crawled_images " +
                     "WHERE resource_id IS NOT NULL AND entity_id IS NOT NULL " +
                     "ORDER BY CASE WHEN file_name != 'default.jpg' THEN 0 ELSE 1 END, " +
                     "crawl_time DESC " +
                     "LIMIT ? OFFSET ?";
        
        int offset = (page - 1) * pageSize;
        return jdbcTemplate.queryForList(sql, pageSize, offset);
    }

    /**
     * 获取资源总数
     */
    public int getTotalResourceCount() {
        String sql = "SELECT COUNT(DISTINCT resource_id) FROM crawled_images " +
                     "WHERE resource_id IS NOT NULL AND entity_id IS NOT NULL";
        Integer count = jdbcTemplate.queryForObject(sql, Integer.class);
        return count != null ? count : 0;
    }

    /**
     * 根据entity_id获取实体信息
     */
    public Map<String, Object> getEntityById(Long entityId) {
        String sql = "SELECT entity_name, description, entity_type, cultural_value " +
                     "FROM cultural_entities WHERE id = ? LIMIT 1";
        List<Map<String, Object>> results = jdbcTemplate.queryForList(sql, entityId);
        return results.isEmpty() ? null : results.get(0);
    }
}

