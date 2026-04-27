package com.modstore.service;

import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.junit.jupiter.api.Assertions.assertFalse;

class WechatPayServiceTest {

    @Test
    void reportsNotConfiguredUntilAllMerchantSecretsArePresent() {
        WechatPayService service = new WechatPayService();
        ReflectionTestUtils.setField(service, "appId", "wx-app");
        ReflectionTestUtils.setField(service, "mchId", "mch-id");
        ReflectionTestUtils.setField(service, "privateKeyPath", "");
        ReflectionTestUtils.setField(service, "merchantSerialNo", "serial");
        ReflectionTestUtils.setField(service, "apiV3Key", "api-v3-key");
        ReflectionTestUtils.setField(service, "notifyUrl", "https://example.com/api/payment/notify/wechat");

        assertFalse(service.configured());
    }
}
