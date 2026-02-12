Page({
  data: {
    isDarkMode: false,
    maxImageSize: 5 * 1024 * 1024 // 5MB
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
        const tempFilePath = res.tempFilePaths[0];
        // 检查图片大小
        this.checkImageSize(tempFilePath);
      }
    })
  },

  // 检查图片大小
  checkImageSize(filePath) {
    wx.getFileInfo({
      filePath: filePath,
      success: (res) => {
        const fileSize = res.size;
        const maxSize = this.data.maxImageSize;
        
        if (fileSize > maxSize) {
          // 图片过大，显示压缩提示
          this.showCompressDialog(filePath, fileSize, maxSize);
        } else {
          // 图片大小正常，直接跳转
          wx.navigateTo({
            url: `/pages/edit/edit?image=${filePath}`
          });
        }
      },
      fail: (err) => {
        console.error('获取文件信息失败:', err);
        // 获取文件信息失败，直接跳转
        wx.navigateTo({
          url: `/pages/edit/edit?image=${filePath}`
        });
      }
    });
  },

  // 显示压缩对话框
  showCompressDialog(filePath, fileSize, maxSize) {
    const fileSizeMB = (fileSize / (1024 * 1024)).toFixed(2);
    const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(2);
    
    wx.showModal({
      title: '图片过大',
      content: `您选择的图片大小为 ${fileSizeMB}MB，超过了 ${maxSizeMB}MB 的限制。是否需要压缩图片？`,
      confirmText: '压缩图片',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          // 用户选择压缩
          this.compressImage(filePath);
        }
      }
    });
  },

  // 压缩图片
  compressImage(filePath) {
    wx.showLoading({
      title: '压缩中...',
    });

    // 使用canvas压缩图片
    this.compressImageWithCanvas(filePath);
  },

  // 使用canvas压缩图片
  compressImageWithCanvas(filePath) {
    // 获取图片信息
    wx.getImageInfo({
      src: filePath,
      success: (imgInfo) => {
        const { width, height } = imgInfo;
        
        // 计算压缩后的尺寸（最大宽度为800）
        const maxWidth = 800;
        let newWidth = width;
        let newHeight = height;
        
        if (width > maxWidth) {
          newWidth = maxWidth;
          newHeight = (height * maxWidth) / width;
        }
        
        // 创建canvas
        const canvasId = 'compressCanvas';
        const query = wx.createSelectorQuery();
        
        // 由于canvas需要在页面中存在，我们使用临时页面方法
        // 这里使用简化的方法：直接使用wx.compressImage
        this.compressWithWxAPI(filePath);
      },
      fail: (err) => {
        console.error('获取图片信息失败:', err);
        wx.hideLoading();
        wx.showToast({
          title: '压缩失败',
          icon: 'none'
        });
      }
    });
  },

  // 使用微信API压缩图片
  compressWithWxAPI(filePath) {
    wx.compressImage({
      src: filePath,
      quality: 60, // 压缩质量
      success: (res) => {
        wx.hideLoading();
        
        // 检查压缩后的图片大小
        wx.getFileInfo({
          filePath: res.tempFilePath,
          success: (fileInfo) => {
            const compressedSize = fileInfo.size;
            const originalSize = this.data.maxImageSize;
            
            if (compressedSize > originalSize) {
              // 压缩后仍然过大，提示用户
              wx.showModal({
                title: '压缩后仍然过大',
                content: '图片压缩后仍然超过限制，建议选择其他图片。',
                showCancel: false,
                success: () => {
                  // 返回主页
                }
              });
            } else {
              // 压缩成功，显示结果并跳转
              const originalSizeMB = (this.data.maxImageSize / (1024 * 1024)).toFixed(2);
              const compressedSizeMB = (compressedSize / (1024 * 1024)).toFixed(2);
              const reduction = ((1 - compressedSize / this.data.maxImageSize) * 100).toFixed(0);
              
              wx.showModal({
                title: '压缩成功',
                content: `图片已从 ${originalSizeMB}MB 压缩至 ${compressedSizeMB}MB，减少了 ${reduction}%`,
                showCancel: false,
                success: () => {
                  // 跳转到编辑页面
                  wx.navigateTo({
                    url: `/pages/edit/edit?image=${res.tempFilePath}`
                  });
                }
              });
            }
          },
          fail: (err) => {
            console.error('获取压缩后文件信息失败:', err);
            // 即使获取文件信息失败，也跳转到编辑页面
            wx.navigateTo({
              url: `/pages/edit/edit?image=${res.tempFilePath}`
            });
          }
        });
      },
      fail: (err) => {
        console.error('压缩图片失败:', err);
        wx.hideLoading();
        wx.showToast({
          title: '压缩失败',
          icon: 'none'
        });
      }
    });
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