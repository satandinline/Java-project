package com.cultural.service;

import com.cultural.dao.CulturalResourceDao;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * 资源服务类
 */
@Service
public class ResourceService {

    @Autowired
    private CulturalResourceDao resourceDao;

    /**
     * 获取首页资源列表
     */
    public Map<String, Object> getHomeResources(int page, int pageSize) {
        Map<String, Object> result = new HashMap<>();
        
        try {
            // 获取所有资源图片
            List<Map<String, Object>> allImages = resourceDao.getHomeResources(1, 10000); // 获取足够多的数据用于分组
            
            // 按resource_id分组，每个资源只保留第一张图片（优先非default图片）
            Map<Long, Map<String, Object>> resourceImages = new LinkedHashMap<>();
            
            for (Map<String, Object> img : allImages) {
                Long resourceId = getLongValue(img.get("resource_id"));
                if (resourceId == null) continue;
                
                String fileName = (String) img.get("file_name");
                boolean isDefault = "default.jpg".equals(fileName);
                
                if (!resourceImages.containsKey(resourceId)) {
                    resourceImages.put(resourceId, img);
                } else {
                    Map<String, Object> existing = resourceImages.get(resourceId);
                    String existingFileName = (String) existing.get("file_name");
                    if ("default.jpg".equals(existingFileName) && !isDefault) {
                        resourceImages.put(resourceId, img);
                    }
                }
            }
            
            // 转换为列表并按时间排序
            List<Map<String, Object>> festivalList = new ArrayList<>(resourceImages.values());
            festivalList.sort((a, b) -> {
                Object timeA = a.get("crawl_time");
                Object timeB = b.get("crawl_time");
                if (timeA == null && timeB == null) return 0;
                if (timeA == null) return 1;
                if (timeB == null) return -1;
                return timeB.toString().compareTo(timeA.toString());
            });
            
            // 分页处理
            int totalCount = festivalList.size();
            int startIdx = (page - 1) * pageSize;
            int endIdx = Math.min(startIdx + pageSize, totalCount);
            List<Map<String, Object>> paginatedImages = festivalList.subList(startIdx, endIdx);
            
            // 构建资源列表
            List<Map<String, Object>> resources = new ArrayList<>();
            for (Map<String, Object> img : paginatedImages) {
                Long entityId = getLongValue(img.get("entity_id"));
                String festivalName = (String) img.get("festival_name");
                
                String entityName = "";
                String description = "";
                
                // 通过entity_id查询实体信息
                if (entityId != null) {
                    Map<String, Object> entityInfo = resourceDao.getEntityById(entityId);
                    if (entityInfo != null) {
                        entityName = (String) entityInfo.getOrDefault("entity_name", "");
                        Object descObj = entityInfo.get("description");
                        if (descObj != null) {
                            description = descObj.toString();
                            if (description.length() > 200) {
                                description = description.substring(0, 200);
                            }
                        }
                    }
                }
                
                // 如果没有实体名称，使用节日名称
                if (entityName == null || entityName.isEmpty()) {
                    entityName = festivalName != null ? festivalName : "未命名资源";
                }
                
                // 构建图片URL
                String storagePath = (String) img.get("storage_path");
                String fileName = (String) img.get("file_name");
                String imageUrl = "/default.jpg";
                
                if (storagePath != null && storagePath.contains("default.jpg")) {
                    imageUrl = "/default.jpg";
                } else if (storagePath != null && storagePath.contains("crawled_images")) {
                    String actualFile = storagePath.substring(storagePath.lastIndexOf("/") + 1);
                    imageUrl = "/api/images/crawled/" + actualFile;
                } else if (fileName != null && !fileName.equals("default.jpg")) {
                    imageUrl = "/api/images/crawled/" + fileName;
                }
                
                Map<String, Object> resource = new HashMap<>();
                resource.put("id", "img_" + img.get("id"));
                resource.put("type", "image");
                resource.put("image_url", imageUrl);
                resource.put("entity_name", entityName);
                resource.put("description", description.isEmpty() ? "暂无简介" : description);
                resource.put("festival_name", festivalName != null ? festivalName : entityName);
                resource.put("source", "crawled_images");
                
                resources.add(resource);
            }
            
            int total = resourceDao.getTotalResourceCount();
            
            Map<String, Object> pagination = new HashMap<>();
            pagination.put("page", page);
            pagination.put("page_size", pageSize);
            pagination.put("total", total);
            pagination.put("total_pages", (total + pageSize - 1) / pageSize);
            
            result.put("success", true);
            result.put("resources", resources);
            result.put("pagination", pagination);
            
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "获取资源失败：" + e.getMessage());
        }
        
        return result;
    }
    
    private Long getLongValue(Object obj) {
        if (obj == null) return null;
        if (obj instanceof Long) return (Long) obj;
        if (obj instanceof Number) return ((Number) obj).longValue();
        try {
            return Long.parseLong(obj.toString());
        } catch (Exception e) {
            return null;
        }
    }
}

