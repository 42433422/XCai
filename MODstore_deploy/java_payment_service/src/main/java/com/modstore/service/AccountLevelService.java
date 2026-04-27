package com.modstore.service;

import com.modstore.model.AccountExperienceLedger;
import com.modstore.model.Order;
import com.modstore.model.User;
import com.modstore.repository.AccountExperienceLedgerRepository;
import com.modstore.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

/**
 * 账号等级与经验体系（Java 端）。
 * 与 Python {@code account_level_service} 保持一致：
 *   - 商品/会员/钱包充值订单按 1 元 = 100 经验入账（钱包充值同样计入）
 *   - 退款成功后扣回相同经验
 *   - 通过 (source_type, source_order_id) 唯一键保证幂等
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AccountLevelService {

    private static final Set<String> COUNTABLE_ORDER_KINDS = Set.of("item", "plan", "wallet");

    private final AccountExperienceLedgerRepository ledgerRepository;
    private final UserRepository userRepository;

    public static long xpFromAmount(BigDecimal amountYuan) {
        if (amountYuan == null) {
            return 0L;
        }
        if (amountYuan.compareTo(BigDecimal.ZERO) <= 0) {
            return 0L;
        }
        BigDecimal xp = amountYuan.multiply(BigDecimal.valueOf(100)).setScale(0, RoundingMode.HALF_UP);
        return xp.longValueExact();
    }

    /**
     * 与 Python {@code account_level_service.is_countable_order} 一致：
     * 有商品 id 或套餐 id 即算消费订单；再按 order_kind 兜底，避免仅因 kind 字段异常/空格漏发经验。
     */
    public static boolean isCountable(Order order) {
        if (order == null) {
            return false;
        }
        if (order.getItemId() != null && order.getItemId() > 0) {
            return true;
        }
        if (order.getPlanId() != null && !order.getPlanId().isBlank()) {
            return true;
        }
        String k = order.getOrderKind() == null ? "" : order.getOrderKind().trim().toLowerCase(Locale.ROOT);
        return !k.isEmpty() && COUNTABLE_ORDER_KINDS.contains(k);
    }

    @Transactional(propagation = Propagation.REQUIRED)
    public long applyOrderXp(Order order) {
        if (!isCountable(order)) {
            return 0L;
        }
        long xp = xpFromAmount(order.getTotalAmount());
        if (xp <= 0) {
            return 0L;
        }
        if (order.getUser() == null || order.getUser().getId() == null) {
            return 0L;
        }
        String outTradeNo = order.getOutTradeNo();
        if (outTradeNo == null || outTradeNo.isBlank()) {
            return 0L;
        }
        Optional<AccountExperienceLedger> existing =
                ledgerRepository.findBySourceTypeAndSourceOrderId("order_paid", outTradeNo);
        if (existing.isPresent()) {
            return 0L;
        }
        AccountExperienceLedger entry = new AccountExperienceLedger();
        entry.setUserId(order.getUser().getId());
        entry.setSourceType("order_paid");
        entry.setSourceOrderId(outTradeNo);
        entry.setAmount(order.getTotalAmount() == null ? BigDecimal.ZERO : order.getTotalAmount());
        entry.setXpDelta(xp);
        entry.setDescription("订单消费经验 (" + outTradeNo + ")");
        try {
            ledgerRepository.save(entry);
        } catch (DataIntegrityViolationException ignore) {
            return 0L;
        }
        adjustUserExperience(order.getUser().getId(), xp);
        log.info("账号经验 +{} userId={} order={} amount={}", xp, order.getUser().getId(), outTradeNo, order.getTotalAmount());
        return xp;
    }

    @Transactional(propagation = Propagation.REQUIRED)
    public long revokeOrderXp(Long userId, String outTradeNo) {
        if (userId == null || outTradeNo == null || outTradeNo.isBlank()) {
            return 0L;
        }
        Optional<AccountExperienceLedger> paid =
                ledgerRepository.findBySourceTypeAndSourceOrderId("order_paid", outTradeNo);
        if (paid.isEmpty()) {
            return 0L;
        }
        Optional<AccountExperienceLedger> refunded =
                ledgerRepository.findBySourceTypeAndSourceOrderId("order_refunded", outTradeNo);
        if (refunded.isPresent()) {
            return 0L;
        }
        long xp = paid.get().getXpDelta();
        if (xp <= 0) {
            return 0L;
        }
        AccountExperienceLedger entry = new AccountExperienceLedger();
        entry.setUserId(userId);
        entry.setSourceType("order_refunded");
        entry.setSourceOrderId(outTradeNo);
        BigDecimal amount = paid.get().getAmount() == null ? BigDecimal.ZERO : paid.get().getAmount().negate();
        entry.setAmount(amount);
        entry.setXpDelta(-xp);
        entry.setDescription("退款扣回经验 (" + outTradeNo + ")");
        try {
            ledgerRepository.save(entry);
        } catch (DataIntegrityViolationException ignore) {
            return 0L;
        }
        adjustUserExperience(userId, -xp);
        log.info("账号经验 -{} userId={} order={}", xp, userId, outTradeNo);
        return xp;
    }

    private void adjustUserExperience(Long userId, long delta) {
        userRepository.findById(userId).ifPresent(user -> {
            long current = user.getExperience();
            long next = Math.max(0L, current + delta);
            user.setExperience(next);
            userRepository.save(user);
        });
    }
}
