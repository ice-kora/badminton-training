/**
 * API base URL for local demo.
 * 微信开发者工具须开启：详情 → 本地设置 → 不校验合法域名...
 * 真机调试请改为电脑局域网 IP，例如 http://192.168.1.8:8000
 *
 * subscribeTemplateId: 订阅消息模板 ID 占位。
 * touristappid 无法真实推送；正式 AppID + 已审核模板后填写。
 * 留空则跳过 wx.requestSubscribeMessage，仅提示「分析完成后可在成长页查看」。
 */
module.exports = {
  baseUrl: 'http://127.0.0.1:8000',
  /** env placeholder — set after WeChat template approval */
  subscribeTemplateId: '',
  /** Mirror API VIDEO_TTL_DAYS — privacy badge copy */
  videoTtlDays: 7,
}
