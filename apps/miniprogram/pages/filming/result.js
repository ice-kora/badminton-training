const { request, ensureLogin } = require('../../utils/request')

Page({
  data: {
    jobId: '',
    videoId: '',
    skillId: '',
    jobStatus: '',
    jobMessage: '',
    errorCode: '',
    error: '',
  },
  onLoad(q) {
    this.setData({
      jobId: q.job_id || '',
      videoId: q.video_id || '',
      skillId: q.skill_id || '',
    })
    if (!q.job_id) return
    ensureLogin()
      .then(() => request({ url: `/analysis/jobs/${q.job_id}`, auth: true }))
      .then((job) => {
        this.setData({
          jobStatus: job.status,
          jobMessage: job.message || '分析能力尚未开放',
          errorCode: job.error_code || '',
        })
      })
      .catch((e) => this.setData({ error: e.message || '加载任务失败' }))
  },
  backSkill() {
    if (this.data.skillId) {
      wx.navigateBack({ delta: 2 })
    } else {
      wx.switchTab({ url: '/pages/skills/tree' })
    }
  },
})
