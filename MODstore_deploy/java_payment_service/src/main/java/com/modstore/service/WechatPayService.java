package com.modstore.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class WechatPayService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final WebClient webClient = WebClient.builder()
            .baseUrl("https://api.mch.weixin.qq.com")
            .build();

    @Value("${wechatpay.app-id:}")
    private String appId;

    @Value("${wechatpay.mch-id:}")
    private String mchId;

    @Value("${wechatpay.private-key-path:}")
    private String privateKeyPath;

    @Value("${wechatpay.merchant-serial-no:}")
    private String merchantSerialNo;

    @Value("${wechatpay.api-v3-key:}")
    private String apiV3Key;

    @Value("${wechatpay.notify-url:}")
    private String notifyUrl;

    public boolean configured() {
        return !blank(appId) && !blank(mchId) && !blank(privateKeyPath)
                && !blank(merchantSerialNo) && !blank(apiV3Key) && !blank(notifyUrl);
    }

    public Map<String, Object> createNativePay(String outTradeNo, String subject, BigDecimal amount) {
        if (!configured()) {
            return Map.of("ok", false, "message", "微信支付未配置");
        }
        try {
            Map<String, Object> amountBody = Map.of("total", amount.movePointRight(2).intValueExact(), "currency", "CNY");
            Map<String, Object> body = new HashMap<>();
            body.put("appid", appId);
            body.put("mchid", mchId);
            body.put("description", subject);
            body.put("out_trade_no", outTradeNo);
            body.put("notify_url", notifyUrl);
            body.put("amount", amountBody);
            String json = objectMapper.writeValueAsString(body);
            String path = "/v3/pay/transactions/native";
            String timestamp = String.valueOf(Instant.now().getEpochSecond());
            String nonce = UUID.randomUUID().toString().replace("-", "");
            String authorization = authorization("POST", path, timestamp, nonce, json);
            Map<String, Object> resp = webClient.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .header("Authorization", authorization)
                    .header("Accept", "application/json")
                    .bodyValue(json)
                    .retrieve()
                    .bodyToMono(new org.springframework.core.ParameterizedTypeReference<Map<String, Object>>() {})
                    .block();
            String codeUrl = String.valueOf(resp == null ? "" : resp.getOrDefault("code_url", ""));
            if (codeUrl.isBlank()) {
                return Map.of("ok", false, "message", "微信支付未返回 code_url");
            }
            return Map.of("ok", true, "type", "wechat_native", "qr_code", codeUrl, "code_url", codeUrl);
        } catch (Exception e) {
            return Map.of("ok", false, "message", "微信支付下单失败: " + e.getMessage());
        }
    }

    public Map<String, Object> decryptNotify(Map<String, Object> body) {
        try {
            Map<String, Object> resource = castMap(body.get("resource"));
            String nonce = String.valueOf(resource.getOrDefault("nonce", ""));
            String associatedData = String.valueOf(resource.getOrDefault("associated_data", ""));
            String ciphertext = String.valueOf(resource.getOrDefault("ciphertext", ""));
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            SecretKeySpec key = new SecretKeySpec(apiV3Key.getBytes(StandardCharsets.UTF_8), "AES");
            cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, nonce.getBytes(StandardCharsets.UTF_8)));
            if (!associatedData.isBlank()) {
                cipher.updateAAD(associatedData.getBytes(StandardCharsets.UTF_8));
            }
            byte[] plain = cipher.doFinal(Base64.getDecoder().decode(ciphertext));
            return objectMapper.readValue(plain, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            throw new IllegalArgumentException("微信支付通知解密失败: " + e.getMessage(), e);
        }
    }

    private String authorization(String method, String path, String timestamp, String nonce, String body) throws Exception {
        String message = method + "\n" + path + "\n" + timestamp + "\n" + nonce + "\n" + body + "\n";
        Signature signature = Signature.getInstance("SHA256withRSA");
        signature.initSign(loadPrivateKey());
        signature.update(message.getBytes(StandardCharsets.UTF_8));
        String signed = Base64.getEncoder().encodeToString(signature.sign());
        return "WECHATPAY2-SHA256-RSA2048 mchid=\"" + mchId
                + "\",nonce_str=\"" + nonce
                + "\",timestamp=\"" + timestamp
                + "\",serial_no=\"" + merchantSerialNo
                + "\",signature=\"" + signed + "\"";
    }

    private PrivateKey loadPrivateKey() throws Exception {
        String pem = Files.readString(Path.of(privateKeyPath), StandardCharsets.UTF_8)
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replaceAll("\\s+", "");
        byte[] der = Base64.getDecoder().decode(pem);
        return KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(der));
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> castMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            return (Map<String, Object>) map;
        }
        return Map.of();
    }

    private boolean blank(String value) {
        return value == null || value.trim().isEmpty();
    }
}
