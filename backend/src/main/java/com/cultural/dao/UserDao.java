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
        String sql = "SELECT id, account, password_hash, role, nickname, signature, " +
                     "avatar_path, security_question, security_answer_hash, created_at " +
                     "FROM users WHERE account = ?";
        List<User> users = jdbcTemplate.query(sql, 
                new BeanPropertyRowMapper<>(User.class), account);
        return users.isEmpty() ? Optional.empty() : Optional.of(users.get(0));
    }

    /**
     * 根据ID查找用户
     */
    public Optional<User> findById(Long id) {
        String sql = "SELECT id, account, password_hash, role, nickname, signature, " +
                     "avatar_path, security_question, security_answer_hash, created_at " +
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
}

