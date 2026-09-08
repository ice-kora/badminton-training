const { request, ensureLogin, getToken, baseUrl } = require('../../utils/request')

Page({
  data: {
    skillId: '',
    guide: null,
    checklist: [
      { key: 'full_body', label: '全身已入镜（对照剪影）', checked: false },
      { key: 'distance_ok', label: '距离合适（不太近/不太远）', checked: false },
      { key: 'racket_visible', label: '球拍可见', checked: false },
      { key: 'portrait', label: '竖屏拍摄', checked: false },
      { key: 'lighting_ok', label: '光线充足、背景干净', checked: false },
    ],
    checkedCount: 0,
    showCamera: false,
    videoPath: '',
    videoInfo: '',
    uploading: false,
    failChecks: [],
    error: '',
  },
  onLoad(q) {
    const skillId = q.skill_id
    if (!skillId) {
      this.setData({ error: '缺少 skill_id' })
      return
    }
    this.setData({ skillId })
    request({ url: `/filming-guides/${skillId}` })
      .then((guides) => {
        if (guides && guides[0]) this.setData({ guide: guides[0] })
      })
      .catch(() => {})
  },
  onChecklistChange(e) {
    const selected = e.detail.value || []
    const checklist = this.data.checklist.map((c) => ({
      ...c,
      checked: selected.indexOf(c.key) !== -1,
    }))
    this.setData({
      checklist,
      checkedCount: selected.length,
    })
  },
  toggleCamera() {
    this.setData({ showCamera: !this.data.showCamera })
  },
  allChecked() {
    return this.data.checklist.every((c) => c.checked)
  },
  chooseMedia() {
    if (!this.allChecked()) {
      wx.showToast({ title: '请先勾选全部清单', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: 1,
      mediaType: ['video'],
      sourceType: ['album', 'camera'],
      maxDuration: 15,
      camera: 'back',
      success: (res) => {
        const f = res.tempFiles[0]
        const dur = Number(f.duration || 0)
        const videoInfo = `约 ${dur.toFixed ? dur.toFixed(1) : dur}s · ${f.width || '?'}x${f.height || '?'}`
        if (dur > 30) {
          this.setData({
            videoPath: f.tempFilePath,
            videoInfo,
            failChecks: [],
            error: `视频约 ${dur.toFixed(1)} 秒，超过 30 秒上限，请换 5–15 秒短视频`,
          })
          wx.showToast({ title: '视频过长，请重选', icon: 'none' })
          return
        }
        this.setData({
          videoPath: f.tempFilePath,
          videoInfo,
          failChecks: [],
          error: '',
        })
      },
      fail: (err) => {
        this.setData({ error: err.errMsg || '选择视频失败' })
      },
    })
  },
  doUpload() {
    if (!this.allChecked()) {
      wx.showToast({ title: '请先勾选全部清单', icon: 'none' })
      return
    }
    if (!this.data.videoPath) {
      wx.showToast({ title: '请先选择视频', icon: 'none' })
      return
    }
    this.setData({ uploading: true, failChecks: [], error: '' })
    const checklistObj = {}
    this.data.checklist.forEach((c) => {
      checklistObj[c.key] = !!c.checked
    })
    ensureLogin()
      .then(() => {
        return new Promise((resolve, reject) => {
          wx.uploadFile({
            url: `${baseUrl}/videos/upload`,
            filePath: this.data.videoPath,
            name: 'file',
            formData: {
              skill_id: String(this.data.skillId),
              client_checklist_json: JSON.stringify(checklistObj),
              frame_coverage_hints_json: JSON.stringify({
                silhouette_guide: true,
                note: 'client silhouette + checklist only; not pose',
              }),
            },
            header: {
              Authorization: `Bearer ${getToken()}`,
            },
            success: (res) => {
              let body = res.data
              try {
                body = JSON.parse(res.data)
              } catch (e) {
                /* keep raw */
              }
              if (res.statusCode >= 200 && res.statusCode < 300) {
                resolve(body)
              } else {
                reject({ statusCode: res.statusCode, body })
              }
            },
            fail: (err) => reject({ message: err.errMsg || '上传失败' }),
          })
        })
      })
      .then((body) => {
        this.setData({ uploading: false })
        const jobId = body.analysis_job && body.analysis_job.id
        const videoId = body.video && body.video.id
        wx.redirectTo({
          url: `/pages/filming/result?job_id=${jobId}&video_id=${videoId}&skill_id=${this.data.skillId}`,
        })
      })
      .catch((err) => {
        this.setData({ uploading: false })
        const detail = (err.body && err.body.detail) || err.body || err
        if (detail && detail.precheck && detail.precheck.checks) {
          const fails = detail.precheck.checks.filter((c) => c.status === 'fail')
          this.setData({
            failChecks: fails,
            error: detail.message || '预检未通过，请重拍',
          })
        } else {
          const msg =
            (detail && (detail.message || detail.detail)) ||
            err.message ||
            '上传失败'
          this.setData({ error: typeof msg === 'string' ? msg : JSON.stringify(msg) })
        }
      })
  },
})
