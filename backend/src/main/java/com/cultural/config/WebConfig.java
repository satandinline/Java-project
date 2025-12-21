package com.cultural.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web配置类
 * 配置CORS跨域和静态资源访问
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    /**
     * 配置CORS跨域
     */
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns("*")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(true);
    }

    /**
     * 配置静态资源访问
     */
    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        // 头像访问路径
        registry.addResourceHandler("/avatars/**")
                .addResourceLocations("file:./public/");
        
        // 默认头像
        registry.addResourceHandler("/default.jpg")
                .addResourceLocations("file:./public/");
        
        // 爬取的图片
        registry.addResourceHandler("/api/images/crawled/**")
                .addResourceLocations("file:./crawled_images/");
        
        // 用户上传的图片
        registry.addResourceHandler("/image_from_users/**")
                .addResourceLocations("file:./uploads/");
        
        // AIGC生成的图片
        registry.addResourceHandler("/AIGC_graph/**")
                .addResourceLocations("file:./AIGC_graph/");
    }
}

