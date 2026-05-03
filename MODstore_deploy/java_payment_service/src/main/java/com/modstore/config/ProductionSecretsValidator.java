package com.modstore.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;
import org.springframework.stereotype.Component;

import java.util.Locale;
import java.util.Set;

/**
 * 生产环境禁止使用示例/默认签名与支付密钥。
 */
@Slf4j
@Component
@Order(0)
public class ProductionSecretsValidator implements ApplicationRunner {

    private static final Set<String> FORBIDDEN_PAYMENT_SECRETS = Set.of(
            "",
            "default_secret_key",
            "changeme",
            "secret"
    );

    private static final Set<String> FORBIDDEN_JWT_SECRETS = Set.of(
            "modstore-dev-secret-change-in-prod",
            "changeme",
            "secret"
    );

    private final Environment environment;

    public ProductionSecretsValidator(Environment environment) {
        this.environment = environment;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!environment.acceptsProfiles(Profiles.of("prod"))) {
            return;
        }
        String paymentKey = environment.getProperty("payment.secret-key", "").trim();
        String jwtSecret = environment.getProperty("jwt.secret", "").trim();

        String paymentNorm = paymentKey.toLowerCase(Locale.ROOT);
        if (FORBIDDEN_PAYMENT_SECRETS.contains(paymentNorm)) {
            fail("PAYMENT_SECRET_KEY / payment.secret-key must not use a default or placeholder value in production");
        }
        String jwtNorm = jwtSecret.toLowerCase(Locale.ROOT);
        if (FORBIDDEN_JWT_SECRETS.contains(jwtNorm) || jwtSecret.length() < 32) {
            fail("MODSTORE_JWT_SECRET / jwt.secret must be a strong value (>= 32 bytes) and not a documented dev default");
        }
        log.info("ProductionSecretsValidator: payment and JWT secrets passed basic policy checks");
    }

    private static void fail(String message) {
        log.error("{}", message);
        throw new IllegalStateException(message);
    }
}
