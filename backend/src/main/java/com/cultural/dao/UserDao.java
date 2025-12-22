package com.cultural.dao;

import com.cultural.entity.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.BeanPropertyRowMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 用户数据访问对象
 */
@Repository
public class UserDao {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    /**
     * 根据账号查找用户
     */
    public Optional<User> findByAccount(String account) {
        // 检查字段是否存在，兼容旧数据库
        String sql = "SELECT id, account, password_hash, role, nickname, signature, " +
                     "avatar_path, security_question, security_answer_hash, " +
                     "COALESCE(is_online, 0) as is_online, last_active_time, created_at " +
                     "FROM users WHERE account = ?";
        List<User> users = jdbcTemplate.query(sql, 
                new BeanPropertyRowMapper<>(User.class), account);
        return users.isEmpty() ? Optional.empty() : Optional.of(users.get(0));
    }

    /**
     * 根据ID查找用户
     */
    public Optional<User> findById(Long id) {
        // 检查字段是否存在，兼容旧数据库
        String sql = "SELECT id, account, password_hash, role, nickname, signature, " +
                     "avatar_path, security_question, security_answer_hash, " +
                     "COALESCE(is_online, 0) as is_online, last_active_time, created_at " +
                     "FROM users WHERE id = ?";
        List<User> users = jdbcTemplate.query(sql, 
                new BeanPropertyRowMapper<>(User.class), id);
        return users.isEmpty() ? Optional.empty() : Optional.of(users.get(0));
    }

    /**
     * 创建用户
     */
    public Long createUser(User user) {
        String sql = "INSERT INTO users (account, password_hash, role, nickname, signature, " +
                     "avatar_path, security_question, security_answer_hash) " +
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
        jdbcTemplate.update(sql, 
                user.getAccount(),
                user.getPasswordHash(),
                user.getRole(),
                user.getNickname(),
                user.getSignature(),
                user.getAvatarPath(),
                user.getSecurityQuestion(),
                user.getSecurityAnswerHash());
        
        // 获取插入的ID
        String getIdSql = "SELECT LAST_INSERT_ID()";
        return jdbcTemplate.queryForObject(getIdSql, Long.class);
    }

    /**
     * 更新用户信息
     */
    public void updateUser(User user) {
        String sql = "UPDATE users SET nickname = ?, signature = ?, avatar_path = ?, " +
                     "security_question = ?, security_answer_hash = ? WHERE id = ?";
        jdbcTemplate.update(sql,
                user.getNickname(),
                user.getSignature(),
                user.getAvatarPath(),
                user.getSecurityQuestion(),
                user.getSecurityAnswerHash(),
                user.getId());
    }

    /**
     * 更新密码
     */
    public void updatePassword(Long userId, String passwordHash) {
        String sql = "UPDATE users SET password_hash = ? WHERE id = ?";
        jdbcTemplate.update(sql, passwordHash, userId);
    }

    /**
     * 删除用户
     */
    public void deleteUser(Long userId) {
        String sql = "DELETE FROM users WHERE id = ?";
        jdbcTemplate.update(sql, userId);
    }

    /**
     * 检查账号是否存在
     */
    public boolean accountExists(String account) {
        String sql = "SELECT COUNT(*) FROM users WHERE account = ?";
        Integer count = jdbcTemplate.queryForObject(sql, Integer.class, account);
        return count != null && count > 0;
    }

    /**
     * 更新用户在线状态
     */
    public void updateOnlineStatus(Long userId, boolean isOnline) {
        // 检查字段是否存在，如果不存在则跳过更新（兼容旧数据库）
        try {
            String sql = "UPDATE users SET is_online = ?, last_active_time = NOW() WHERE id = ?";
            jdbcTemplate.update(sql, isOnline ? 1 : 0, userId);
        } catch (Exception e) {
            // 如果字段不存在，忽略错误（兼容旧数据库）
            System.out.println("更新在线状态失败（可能字段不存在）: " + e.getMessage());
        }
    }

    /**
     * 更新用户角色
     */
    public void updateUserRole(Long userId, String role) {
        String sql = "UPDATE users SET role = ? WHERE id = ?";
        jdbcTemplate.update(sql, role, userId);
    }

    /**
     * 获取所有用户列表（按指定排序）
     * 排序规则：在线用户在前，离线用户在后；每类中管理员在前，普通用户在后；同状态同身份按账号升序
     */
    public List<User> getAllUsers() {
        // 兼容旧数据库，如果is_online字段不存在则使用0
        String sql = "SELECT id, account, password_hash, role, nickname, signature, " +
                     "avatar_path, security_question, security_answer_hash, " +
                     "COALESCE(is_online, 0) as is_online, last_active_time, created_at " +
                     "FROM users " +
                     "ORDER BY " +
                     "  CASE WHEN COALESCE(is_online, 0) = 1 THEN 0 ELSE 1 END, " +  // 在线在前
                     "  CASE WHEN role = '超级管理员' THEN 0 " +
                     "       WHEN role = '管理员' THEN 1 " +
                     "       ELSE 2 END, " +  // 超级管理员 > 管理员 > 普通用户
                     "  account ASC";  // 同状态同身份按账号升序
        return jdbcTemplate.query(sql, new BeanPropertyRowMapper<>(User.class));
    }
}

