const { request, ensureLogin } = require('../../utils/request')

Page({
  data: {
    jobId: '',
    videoId: '',
    skillId: '',
    jobStatus: '',
    jobMessage: '',
    errorCode: '',
    poseLabel: '关键点未提取',
    scoringLabel: '评分未开放',
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
        const poseOk = job.status === 'pose_extracted'
        this.setData({
          jobStatus: job.status,
          jobMessage: job.message || '评分未开放',
          errorCode: job.error_code || '',
          poseLabel: poseOk ? '关键点已提取' : (job.status === 'queued' ? '关键点排队中' : '关键点未提取'),
          scoringLabel: '评分未开放',
        })
      })
      .catch((e) => this.setData({ error: e.message || '加载任务失败' }))
  },
  goDetail() {
    if (!this.data.videoId) {
      wx.showToast({ title: '无视频 ID', icon: 'none' })
      return
    }
    wx.navigateTo({ url: `/pages/records/detail?id=${this.data.videoId}` })
  },
  goHistory() {
    wx.switchTab({ url: '/pages/records/index' })
  },
  backSkill() {
    if (this.data.skillId) {
      wx.navigateBack({ delta: 2 })
    } else {
      wx.switchTab({ url: '/pages/skills/tree' })
    }
  },
})
