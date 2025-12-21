package com.cultural;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;

/**
 * 公共文化资源系统后端应用主类
 */
@SpringBootApplication
@EnableConfigurationProperties
public class CulturalResourcesApplication {

    public static void main(String[] args) {
        SpringApplication.run(CulturalResourcesApplication.class, args);
        System.out.println("=".repeat(60));
        System.out.println("公共文化资源系统后端服务已启动");
        System.out.println("服务器地址: http://localhost:8000");
        System.out.println("=".repeat(60));
    }
}

