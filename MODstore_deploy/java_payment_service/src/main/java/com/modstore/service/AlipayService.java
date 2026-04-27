package com.modstore.service;

import com.alipay.api.AlipayApiException;
import com.alipay.api.AlipayClient;
import com.alipay.api.AlipayResponse;
import com.alipay.api.request.AlipayTradePagePayRequest;
import com.alipay.api.request.AlipayTradePrecreateRequest;
import com.alipay.api.request.AlipayTradeQueryRequest;
import com.alipay.api.request.AlipayTradeWapPayRequest;
import com.alipay.api.response.AlipayTradePagePayResponse;
import com.alipay.api.response.AlipayTradePrecreateResponse;
import com.alipay.api.response.AlipayTradeQueryResponse;
import com.alipay.api.response.AlipayTradeWapPayResponse;
import com.alipay.api.internal.util.AlipaySignature;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.modstore.util.MoneyUtils;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;

@Slf4j
@Service
@RequiredArgsConstructor
public class AlipayService {

    private final AlipayClient alipayClient;
    private final ObjectMapper objectMapper;

    @Value("${alipay.public-key}")
    private String alipayPublicKey;

    @Value("${alipay.notify-url:}")
    private String notifyUrl;

    private String bizContentJson(Map<String, Object> bizContent) {
        try {
            return objectMapper.writeValueAsString(bizContent);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("支付宝 biz_content 序列化失败", e);
        }
    }

    private void applyNotifyUrl(AlipayTradePagePayRequest request) {
        if (notifyUrl != null && !notifyUrl.isBlank()) {
            request.setNotifyUrl(notifyUrl.trim());
        }
    }

    private void applyNotifyUrl(AlipayTradeWapPayRequest request) {
        if (notifyUrl != null && !notifyUrl.isBlank()) {
            request.setNotifyUrl(notifyUrl.trim());
        }
    }

    private void applyNotifyUrl(AlipayTradePrecreateRequest request) {
        if (notifyUrl != null && !notifyUrl.isBlank()) {
            request.setNotifyUrl(notifyUrl.trim());
        }
    }

    private static String firstNonBlank(String... parts) {
        if (parts == null) {
            return null;
        }
        for (String p : parts) {
            if (p != null && !p.isBlank()) {
                return p.trim();
            }
        }
        return null;
    }

    /** 网关返回 isSuccess=false 时的可读说明（sub_msg/msg/code 常有一个非空）。 */
    private static String alipayResponseFailureMessage(AlipayResponse r) {
        if (r == null) {
            return "支付宝无有效响应";
        }
        String line = firstNonBlank(r.getSubMsg(), r.getMsg());
        if (line != null) {
            return truncate(line, 240);
        }
        String code = firstNonBlank(r.getSubCode(), r.getCode());
        if (code != null) {
            return truncate("支付宝返回码: " + code, 240);
        }
        return "支付宝拒绝下单（无 sub_msg/msg，请查服务端日志）";
    }

    /**
     * SDK 抛 AlipayApiException 时的用户可见说明。
     * 部分环境（TLS/代理/密钥格式）下 getErrMsg/getMessage 可能为空，需串联 cause 与 errCode。
     */
    /**
     * 支付宝/SDK 常返回「支付请求失败」等笼统句；补充固定排查提示，避免前端只显示半句。
     */
    private static String enrichGenericAlipayMessage(String line) {
        if (line == null || line.isBlank()) {
            return line;
        }
        String t = line.trim();
        boolean vague = t.length() <= 32
                && (t.contains("支付请求失败") || t.contains("系统繁忙") || t.contains("系统异常") || t.contains("未知错误"));
        if (!vague) {
            return line;
        }
        return t + " — 请核对：ALIPAY_APP_ID；应用 RSA2 私钥与支付宝公钥（路径或内容）；ALIPAY_DEBUG 与沙箱/正式是否一致；"
                + "服务器能否访问支付宝网关；以及 Java 日志中的 AlipayApiException 堆栈。";
    }

    private static String alipayExceptionUserMessage(AlipayApiException e) {
        String direct = firstNonBlank(e.getErrMsg(), e.getMessage());
        if (direct != null) {
            String low = direct.toLowerCase();
            if (low.contains("私钥") && (low.contains("invalidkey") || low.contains("format") || low.contains("rs"))) {
                return "应用私钥无法被 SDK 用于 RSA2 签名。请用开放平台「接口加签方式」中与本应用成对的**应用私钥**原样上传服务器"
                        + " `keys/app_private_key.pem`（可 PEM 或去头尾的单行 base64，勿手打漏字）；在服务器上可用"
                        + " `openssl pkey -in app_private_key.pem -text -noout` 或 DER 解出后校验。原始："
                        + truncate(direct.trim(), 180);
            }
            if (low.contains("sign check") || low.contains("sign and data")) {
                return "支付宝同步返回验签失败：① ALIPAY_ALIPAY_PUBLIC_KEY / ALIPAY_PUBLIC_KEY 必须是开放平台"
                        + "「支付宝公钥」(RSA2)，不能填「应用公钥」；② 正式环境须 ALIPAY_DEBUG=0 且 APPID、"
                        + "应用私钥、支付宝公钥均为正式；沙箱须 ALIPAY_DEBUG=1 且三者均为沙箱；③ 密钥 PEM 勿含 BOM。"
                        + " 原始信息：" + truncate(direct.trim(), 160);
            }
            return enrichGenericAlipayMessage(truncate(direct, 240));
        }
        String code = e.getErrCode();
        if (code != null && !code.isBlank()) {
            return truncate("支付宝错误码: " + code.trim(), 240);
        }
        Throwable c = e.getCause();
        while (c != null) {
            String cm = c.getMessage();
            if (cm != null && !cm.isBlank()) {
                return enrichGenericAlipayMessage(truncate(cm.trim(), 240));
            }
            c = c.getCause();
        }
        return "支付请求失败：未取到支付宝错误详情。请核对 ALIPAY_APP_ID、RSA2 私钥与支付宝公钥、ALIPAY_DEBUG、"
                + "ALIPAY_NOTIFY_URL 以及服务器到 openapi 的网络；并查看 Java 日志。";
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max) + "…";
    }

    /**
     * SDK 内部可能用 RuntimeException/InvocationTargetException 包装 {@link AlipayApiException}，仅 catch 其类型会漏掉，导致控制层只返回「系统内部错误」。
     */
    private static AlipayApiException findAlipayApiException(Throwable t) {
        for (Throwable c = t; c != null; c = c.getCause()) {
            if (c instanceof AlipayApiException) {
                return (AlipayApiException) c;
            }
        }
        return null;
    }

    private void putAlipayExecuteError(Map<String, Object> result, String logMessage, Exception e) {
        AlipayApiException alipay = findAlipayApiException(e);
        if (alipay != null) {
            log.error(logMessage, e);
            result.put("ok", false);
            result.put("message", alipayExceptionUserMessage(alipay));
        } else {
            log.error(logMessage + "（非 AlipayApiException）", e);
            result.put("ok", false);
            result.put("message", truncate("支付失败：" + (e.getMessage() == null || e.getMessage().isBlank()
                    ? e.getClass().getSimpleName()
                    : e.getMessage()), 220));
        }
    }

    public Map<String, Object> createPagePay(String outTradeNo, String subject, BigDecimal totalAmount, String returnUrl) {
        Map<String, Object> result = new HashMap<>();
        AlipayTradePagePayRequest pagePayRequest = new AlipayTradePagePayRequest();
        applyNotifyUrl(pagePayRequest);
        try {
            pagePayRequest.setReturnUrl(returnUrl);

            Map<String, Object> bizContent = new TreeMap<>();
            bizContent.put("out_trade_no", outTradeNo);
            bizContent.put("product_code", "FAST_INSTANT_TRADE_PAY");
            bizContent.put("subject", subject);
            bizContent.put("total_amount", MoneyUtils.alipayTotalAmount(totalAmount));

            pagePayRequest.setBizContent(bizContentJson(bizContent));
            // GET：getBody() 为完整跳转 URL，前端 window.location 可用；默认 POST 为 HTML 表单，勿当 URL 用。
            AlipayTradePagePayResponse response = alipayClient.pageExecute(pagePayRequest, "GET");

            if (response.isSuccess()) {
                result.put("ok", true);
                result.put("type", "page");
                result.put("redirect_url", response.getBody());
            } else {
                result.put("ok", false);
                result.put("message", alipayResponseFailureMessage(response));
            }
        } catch (Exception e) {
            putAlipayExecuteError(result, "支付宝PC支付失败", e);
        }
        return result;
    }

    public Map<String, Object> createWapPay(String outTradeNo, String subject, BigDecimal totalAmount, String returnUrl, String quitUrl) {
        Map<String, Object> result = new HashMap<>();
        AlipayTradeWapPayRequest wapPayRequest = new AlipayTradeWapPayRequest();
        applyNotifyUrl(wapPayRequest);
        try {
            wapPayRequest.setReturnUrl(returnUrl);

            Map<String, Object> bizContent = new TreeMap<>();
            bizContent.put("out_trade_no", outTradeNo);
            bizContent.put("product_code", "QUICK_WAP_WAY");
            bizContent.put("subject", subject);
            bizContent.put("total_amount", MoneyUtils.alipayTotalAmount(totalAmount));
            if (quitUrl != null && !quitUrl.isBlank()) {
                bizContent.put("quit_url", quitUrl);
            }

            wapPayRequest.setBizContent(bizContentJson(bizContent));
            AlipayTradeWapPayResponse response = alipayClient.pageExecute(wapPayRequest, "GET");

            if (response.isSuccess()) {
                result.put("ok", true);
                result.put("type", "wap");
                result.put("redirect_url", response.getBody());
            } else {
                result.put("ok", false);
                result.put("message", alipayResponseFailureMessage(response));
            }
        } catch (Exception e) {
            putAlipayExecuteError(result, "支付宝手机支付失败", e);
        }
        return result;
    }

    public Map<String, Object> createPrecreatePay(String outTradeNo, String subject, BigDecimal totalAmount) {
        Map<String, Object> result = new HashMap<>();
        AlipayTradePrecreateRequest precreateRequest = new AlipayTradePrecreateRequest();
        applyNotifyUrl(precreateRequest);
        try {
            Map<String, Object> bizContent = new TreeMap<>();
            bizContent.put("out_trade_no", outTradeNo);
            bizContent.put("subject", subject);
            bizContent.put("total_amount", MoneyUtils.alipayTotalAmount(totalAmount));

            precreateRequest.setBizContent(bizContentJson(bizContent));
            AlipayTradePrecreateResponse response = alipayClient.execute(precreateRequest);

            if (response.isSuccess()) {
                result.put("ok", true);
                result.put("type", "precreate");
                result.put("qr_code", response.getQrCode());
            } else {
                result.put("ok", false);
                result.put("message", alipayResponseFailureMessage(response));
            }
        } catch (Exception e) {
            putAlipayExecuteError(result, "支付宝扫码支付失败", e);
        }
        return result;
    }

    public Map<String, Object> queryOrder(String outTradeNo) {
        Map<String, Object> result = new HashMap<>();
        AlipayTradeQueryRequest queryRequest = new AlipayTradeQueryRequest();
        try {
            Map<String, Object> bizContent = new TreeMap<>();
            bizContent.put("out_trade_no", outTradeNo);

            queryRequest.setBizContent(bizContentJson(bizContent));
            AlipayTradeQueryResponse response = alipayClient.execute(queryRequest);

            if (response.isSuccess()) {
                result.put("ok", true);
                result.put("trade_status", response.getTradeStatus());
                result.put("trade_no", response.getTradeNo());
                result.put("buyer_id", response.getBuyerUserId());
                result.put("total_amount", response.getTotalAmount());
            } else {
                result.put("ok", false);
                result.put("message", alipayResponseFailureMessage(response));
            }
        } catch (Exception e) {
            putAlipayExecuteError(result, "查询订单失败", e);
        }
        return result;
    }

    public boolean verifyNotify(Map<String, String> params) {
        try {
            return AlipaySignature.rsaCheckV1(params, alipayPublicKey, "utf-8", "RSA2");
        } catch (Exception e) {
            log.error("验签失败", e);
            return false;
        }
    }
}
