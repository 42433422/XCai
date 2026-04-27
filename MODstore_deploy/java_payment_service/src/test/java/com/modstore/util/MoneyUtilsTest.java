package com.modstore.util;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;

class MoneyUtilsTest {

    @Test
    void toIntYuanHalfUp_roundsToIntegerYuan() {
        assertThat(MoneyUtils.toIntYuanHalfUp(new BigDecimal("9.40"))).isEqualTo(9);
        assertThat(MoneyUtils.toIntYuanHalfUp(new BigDecimal("9.50"))).isEqualTo(10);
        assertThat(MoneyUtils.toIntYuanHalfUp(new BigDecimal("9.90"))).isEqualTo(10);
        assertThat(MoneyUtils.toIntYuanHalfUp(new BigDecimal("199.00"))).isEqualTo(199);
        assertThat(MoneyUtils.toIntYuanHalfUp(null)).isEqualTo(0);
        assertThat(MoneyUtils.toIntYuanHalfUp(BigDecimal.ZERO)).isEqualTo(0);
    }
}
