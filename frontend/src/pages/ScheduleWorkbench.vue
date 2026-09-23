<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { postJSON } from '../api'

const EXPIRY_MARGIN_SEC = 8

const principal = ref(800000)
const annual_rate = ref(4.2)
const months = ref(360)

const precheck = ref(null)   // {receipt_code, expires_at, monthly_payment, total_interest, snapshot}
const persisted = ref(null)  // {run_id, monthly_payment, total_interest}
const errMsg = ref('')
const prechecking = ref(false)
const persisting = ref(false)
const nowTick = ref(Date.now())
let timer = null

const inputValid = computed(() =>
  Number.isFinite(principal.value) && principal.value > 0 &&
  Number.isFinite(annual_rate.value) && annual_rate.value >= 0 &&
  Number.isInteger(months.value) && months.value > 0)

const snapshot = computed(() =>
  JSON.stringify([Number(principal.value), Number(annual_rate.value), Number(months.value)]))

const stale = computed(() =>
  !!precheck.value && precheck.value.snapshot !== snapshot.value)

const remainingSec = computed(() => {
  if (!precheck.value) return null
  return Math.max(0, Math.floor((new Date(precheck.value.expires_at).getTime() - nowTick.value) / 1000))
})

const receiptState = computed(() => {
  if (!precheck.value) return 'none'
  if (stale.value) return 'stale'
  const s = remainingSec.value
  if (s <= 0) return 'expired'
  if (s <= EXPIRY_MARGIN_SEC) return 'warn'
  return 'ok'
})

const badge = computed(() => ({
  none: '',
  ok: `回执有效 · 剩余 ${remainingSec.value}s`,
  warn: `即将到期 · 剩余 ${remainingSec.value}s，请尽快确认或重新预检`,
  expired: '回执已过期，请重新预检',
  stale: '输入已变更，请重新预检',
}[receiptState.value]))

const canConfirm = computed(() =>
  !!precheck.value && receiptState.value === 'ok' && !persisting.value)

const stopTimer = () => {
  if (timer) { clearInterval(timer); timer = null }
}
watch(precheck, (v) => {
  stopTimer()
  nowTick.value = Date.now()
  if (v) timer = setInterval(() => { nowTick.value = Date.now() }, 1000)
})
onUnmounted(stopTimer)

const errCodeMap = {
  receipt_missing: '缺少预检回执码，请先预检再落库',
  receipt_not_found: '回执码无效，请重新预检',
  receipt_used: '回执码已被使用，请重新预检',
  receipt_expired: '回执码已过截止时间，请重新预检',
  fingerprint_mismatch: '当前输入与预检时不一致，请重新预检',
  loan_mismatch: '关联贷款与预检时不一致，请重新预检',
  payment_mismatch: '月供与预检结果不一致，请重新预检',
}

const showError = (e) => {
  let code = ''
  try { code = JSON.parse(e.message)?.detail?.code || '' } catch { /* 非 JSON 错误体 */ }
  errMsg.value = (code && errCodeMap[code]) || e.message || '请求失败'
}

const doPrecheck = async () => {
  errMsg.value = ''
  prechecking.value = true
  try {
    const data = await postJSON('/api/schedule/precheck', {
      principal: principal.value,
      annual_rate: annual_rate.value,
      months: months.value,
    })
    precheck.value = { ...data, snapshot: snapshot.value }
    persisted.value = null
  } catch (e) {
    precheck.value = null
    showError(e)
  } finally {
    prechecking.value = false
  }
}

const doPersist = async () => {
  if (!canConfirm.value) return
  errMsg.value = ''
  persisting.value = true
  const code = precheck.value.receipt_code
  try {
    const data = await postJSON('/api/schedule', {
      principal: principal.value,
      annual_rate: annual_rate.value,
      months: months.value,
      persist: true,
      receipt_code: code,
    })
    persisted.value = data
    precheck.value = null
  } catch (e) {
    // 任何落库拒绝都意味着回执不可再用，必须重新预检
    precheck.value = null
    showError(e)
  } finally {
    persisting.value = false
  }
}
</script>

<template>
  <div class="page">
    <h1>等额本息试算</h1>
    <div class="form-row">
      <label>本金 <input v-model.number="principal" type="number" min="1" /></label>
      <label>年利率% <input v-model.number="annual_rate" type="number" min="0" step="0.01" /></label>
      <label>月数 <input v-model.number="months" type="number" min="1" max="600" step="1" /></label>
    </div>
    <p v-if="!inputValid" class="hint">请填写合法的本金、年利率与整数月数</p>

    <div class="actions">
      <button :disabled="!inputValid || prechecking" @click="doPrecheck">
        {{ prechecking ? '预检中…' : '① 预检' }}
      </button>
      <button class="btn-confirm" :disabled="!canConfirm" @click="doPersist">
        {{ persisting ? '落库中…' : '② 确认落库' }}
      </button>
    </div>

    <div v-if="errMsg" class="error-banner">{{ errMsg }}</div>

    <div v-if="precheck" class="receipt-panel">
      <div class="receipt-head">
        <span class="badge" :class="'badge-' + receiptState.value">{{ badge }}</span>
      </div>
      <p>预检月供 <span class="hero-num">{{ precheck.monthly_payment }}</span>
         · 利息合计 {{ precheck.total_interest }}</p>
      <p class="hint">回执码 {{ precheck.receipt_code }}（一次性，落库后即作废）</p>
    </div>

    <div v-if="persisted" class="result-panel">
      <p>已落库，记录 #{{ persisted.run_id }} · 月供
        <span class="hero-num">{{ persisted.monthly_payment }}</span>
        · 利息合计 {{ persisted.total_interest }}</p>
      <p class="hint">回执已作废；修改输入后可重新预检。</p>
    </div>
  </div>
</template>
