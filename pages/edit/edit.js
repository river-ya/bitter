Page({
  data: {
    imagePath: '',
    filterType: 'normal', // 当前选择的滤镜类型：normal/bitter
    currentEffect: '', // 当前选中的苦瓜脸特效
    currentFilter: 'normal', // 当前选中的普通滤镜
    serverUrl: 'http://192.168.1.96:5000',  // 已替换为本机局域网 IPv4
    filters: [
      { id: 'normal', name: '原图' },
      { id: 'grayscale', name: '黑白' }, 
      { id: 'sepia', name: '复古' },
      { id: 'brightness', name: '明亮' },
      { id: 'contrast', name: '对比度' }
    ],
    filterValues: {
      grayscale: 0,
      sepia: 0,
      brightness: 0,
      contrast: 0
    },
    originalImagePath: '', // 保存原始图片路径
    maxImageSize: 5 * 1024 * 1024 // 5MB
  },

  getCurrentFilterName() {
    const { filters, currentFilter } = this.data;
    const filter = filters.find(f => f.id === currentFilter);
    return filter ? filter.name : '';
  },
  onLoad(options) {
    if (options.image) {
      this.setData({
        imagePath: options.image,
        originalImagePath: options.image
      });
      
      // 检查图片大小
      this.checkAndCompressImage(options.image);
    }
  },

  // 切换滤镜类型
  switchFilterType(e) {
    const type = e.currentTarget.dataset.type;
    this.setData({ 
      filterType: type,
      currentEffect: '',
      currentFilter: 'normal'
    });
  },

  // 选择滤镜
  selectFilter(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({
      currentFilter: id
    });
    this.updateFilterStyle();
  },

  // 调整滤镜强度
  adjustFilter(e) {
    const value = e.detail.value;
    const filter = this.data.currentFilter;
    
    if (filter === 'normal') return;
    
    const filterValues = {...this.data.filterValues};
    filterValues[filter] = value;
    
    this.setData({ filterValues }, () => {
      this.updateFilterStyle();
    });
  },

  // 更新滤镜样式
  updateFilterStyle() {
    const { filterValues } = this.data;
    let filterStyle = '';
    
    if (this.data.currentFilter !== 'normal') {
      switch(this.data.currentFilter) {
        case 'grayscale':
          filterStyle = `grayscale(${filterValues.grayscale}%)`;
          break;
        case 'sepia':
          filterStyle = `sepia(${filterValues.sepia}%)`;
          break;
        case 'brightness':
          filterStyle = `brightness(${100 + filterValues.brightness}%)`;
          break;
        case 'contrast':
          filterStyle = `contrast(${100 + filterValues.contrast}%)`;
          break;
      }
    }
    
    this.setData({ filterStyle });
  },

  // 选择苦瓜脸特效
  selectEffect(e) {
    const effect = e.currentTarget.dataset.effect;
    
    // 如果再次点击当前效果，恢复原图
    if (this.data.currentEffect === effect) {
      this.setData({
        currentEffect: '',
        imagePath: this.data.originalImagePath || this.data.imagePath
      });
      return;
    }
    
    // 第一次应用效果时，保存原图路径
    if (!this.data.originalImagePath) {
      this.setData({
        originalImagePath: this.data.imagePath
      });
    }

    this.setData({ currentEffect: effect });
    
    wx.showLoading({ title: '处理中...' });
    // 将图片转为base64
    wx.getFileSystemManager().readFile({
      filePath: this.data.imagePath,
      encoding: 'base64',
      success: (res) => {
        // 调用后端API应用特效
        wx.request({
          url: `${this.data.serverUrl}/apply_filter`,  // 替换为你的服务器地址
          method: 'POST',
          data: {
            image: res.data,
            style: effect,
            intensity: 1.0
          },
          success: (res) => {
            if (res.data.image) {
              // 将base64图片保存为临时文件
              const buffer = wx.base64ToArrayBuffer(res.data.image);
              const tempFilePath = `${wx.env.USER_DATA_PATH}/temp_${Date.now()}.jpg`;
              
              wx.getFileSystemManager().writeFile({
                filePath: tempFilePath,
                data: buffer,
                encoding: 'binary',
                success: () => {
                  this.setData({
                    imagePath: tempFilePath
                  });
                },
                fail: (err) => {
                  console.error('保存图片失败:', err);
                  wx.showToast({
                    title: '处理失败',
                    icon: 'none'
                  });
                }
              });
            }
          },
          fail: (err) => {
            console.error('请求失败:', err);
            wx.showToast({
              title: '网络错误',
              icon: 'none'
            });
          },
          complete: () => {
            wx.hideLoading();
          }
        });
      },
      fail: (err) => {
        console.error('读取图片失败:', err);
        wx.hideLoading();
        wx.showToast({
          title: '图片处理失败',
          icon: 'none'
        });
      }
    });
  },

  // 保存图片
  saveImage() {
    wx.saveImageToPhotosAlbum({
      filePath: this.data.imagePath,
      success: () => {
        wx.showToast({
          title: '保存成功',
          icon: 'success'
        });
      }
    });
  },

  // 返回首页
  goBack() {
    wx.navigateBack();
  },

  // 检查并压缩图片
  checkAndCompressImage(filePath) {
    wx.getFileInfo({
      filePath: filePath,
      success: (res) => {
        const fileSize = res.size;
        const maxSize = this.data.maxImageSize;
        
        if (fileSize > maxSize) {
          // 图片过大，显示压缩提示
          this.showCompressDialog(filePath, fileSize, maxSize);
        }
      },
      fail: (err) => {
        console.error('获取文件信息失败:', err);
      }
    });
  },

  // 显示压缩对话框
  showCompressDialog(filePath, fileSize, maxSize) {
    const fileSizeMB = (fileSize / (1024 * 1024)).toFixed(2);
    const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(2);
    
    wx.showModal({
      title: '图片过大',
      content: `当前图片大小为 ${fileSizeMB}MB，超过了 ${maxSizeMB}MB 的限制。是否需要压缩图片以提升处理速度？`,
      confirmText: '压缩图片',
      cancelText: '保持原样',
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
            
            // 压缩成功，显示结果
            const originalSizeMB = (this.data.maxImageSize / (1024 * 1024)).toFixed(2);
            const compressedSizeMB = (compressedSize / (1024 * 1024)).toFixed(2);
            const reduction = ((1 - compressedSize / this.data.maxImageSize) * 100).toFixed(0);
            
            wx.showModal({
              title: '压缩成功',
              content: `图片已从 ${originalSizeMB}MB 压缩至 ${compressedSizeMB}MB，减少了 ${reduction}%。是否使用压缩后的图片？`,
              confirmText: '使用压缩图',
              cancelText: '使用原图',
              success: (modalRes) => {
                if (modalRes.confirm) {
                  // 使用压缩后的图片
                  this.setData({
                    imagePath: res.tempFilePath,
                    originalImagePath: res.tempFilePath
                  });
                  // 重置滤镜和特效
                  this.setData({
                    currentEffect: '',
                    currentFilter: 'normal',
                    filterStyle: ''
                  });
                }
              }
            });
          },
          fail: (err) => {
            console.error('获取压缩后文件信息失败:', err);
            // 即使获取文件信息失败，也提示用户
            wx.showToast({
              title: '压缩完成',
              icon: 'success'
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
  }
}); 