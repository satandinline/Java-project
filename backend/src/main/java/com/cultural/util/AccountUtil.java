package com.cultural.util;

import java.util.Random;

/**
 * 账号工具类
 * 提供账号生成功能
 */
public class AccountUtil {

    private static final Random random = new Random();

    /**
     * 生成随机账号（8-10位数字字符串）
     * 第一位不能是0
     */
    public static String generateRandomAccount() {
        int length = random.nextInt(3) + 8; // 8-10位
        int firstDigit = random.nextInt(9) + 1; // 1-9
        StringBuilder account = new StringBuilder();
        account.append(firstDigit);
        for (int i = 1; i < length; i++) {
            account.append(random.nextInt(10));
        }
        return account.toString();
    }

    /**
     * 生成随机昵称（10位英文字符）
     */
    public static String generateRandomNickname() {
        String chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
        StringBuilder nickname = new StringBuilder();
        for (int i = 0; i < 10; i++) {
            nickname.append(chars.charAt(random.nextInt(chars.length())));
        }
        return nickname.toString();
    }
}

