package com.modstore.config;

import org.junit.jupiter.api.Test;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.mock.env.MockEnvironment;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ProductionSecretsValidatorTest {

    @Test
    void prodProfile_rejectsDefaultPaymentSecret() {
        MockEnvironment env = new MockEnvironment();
        env.setActiveProfiles("prod");
        env.setProperty("payment.secret-key", "default_secret_key");
        env.setProperty("jwt.secret", "01234567890123456789012345678901");
        ProductionSecretsValidator v = new ProductionSecretsValidator(env);
        assertThatThrownBy(() -> v.run(new DefaultApplicationArguments()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("PAYMENT_SECRET_KEY");
    }

    @Test
    void prodProfile_rejectsDocumentedDevJwtDefault() {
        MockEnvironment env = new MockEnvironment();
        env.setActiveProfiles("prod");
        env.setProperty("payment.secret-key", "strong-payment-secret-not-in-denylist-xyz");
        env.setProperty("jwt.secret", "modstore-dev-secret-change-in-prod");
        ProductionSecretsValidator v = new ProductionSecretsValidator(env);
        assertThatThrownBy(() -> v.run(new DefaultApplicationArguments()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("MODSTORE_JWT_SECRET");
    }

    @Test
    void nonProdProfile_skipsValidation() {
        MockEnvironment env = new MockEnvironment();
        env.setActiveProfiles("dev");
        env.setProperty("payment.secret-key", "default_secret_key");
        env.setProperty("jwt.secret", "short");
        ProductionSecretsValidator v = new ProductionSecretsValidator(env);
        v.run(new DefaultApplicationArguments());
    }
}
