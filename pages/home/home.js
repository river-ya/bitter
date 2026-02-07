Page({
  data: {
    isDarkMode: false
  },

  // 跳转到拍照页面
  goToCamera() {
    wx.navigateTo({
      url: '/pages/index/index'
    })
  },

  // 跳转到修图页面
  goToEdit() {
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album'],
      success: (res) => {
        wx.navigateTo({
          url: `/pages/edit/edit?image=${res.tempFilePaths[0]}`
        })
      }
    })
  },

  toggleTheme() {
    const newMode = !this.data.isDarkMode;
    console.log('切换主题模式:', newMode ? '深色模式' : '浅色模式');
    
    this.setData({
      isDarkMode: newMode
    }, () => {
      // 回调确认设置成功
      console.log('主题设置已更新:', this.data.isDarkMode ? '深色模式' : '浅色模式');
    });
    
    // 保存主题设置到本地存储
    wx.setStorageSync('isDarkMode', newMode);
  },

  onLoad() {
    // 读取本地存储的主题设置
    const isDarkMode = wx.getStorageSync('isDarkMode') || false;
    this.setData({
      isDarkMode: isDarkMode
    });
  }
}) 