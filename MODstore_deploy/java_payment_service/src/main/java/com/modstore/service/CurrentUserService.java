package com.modstore.service;

import com.modstore.model.User;
import com.modstore.repository.UserRepository;
import com.modstore.security.AuthenticatedUser;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class CurrentUserService {

    private final UserRepository userRepository;

    @Transactional
    public User requireCurrentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof AuthenticatedUser principal)) {
            throw new IllegalStateException("未登录或登录已过期");
        }
        return userRepository.findById(principal.id())
                .orElseGet(() -> provisionUser(principal));
    }

    private User provisionUser(AuthenticatedUser principal) {
        User user = new User();
        user.setId(principal.id());
        user.setUsername("user_" + principal.id());
        user.setPasswordHash("external-jwt");
        user.setAdmin(false);
        user.setCreatedAt(LocalDateTime.now());
        return userRepository.saveAndFlush(user);
    }
}
