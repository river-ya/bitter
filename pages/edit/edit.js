Page({
  data: {
    imagePath: '',
    filterType: 'normal', // 当前选择的滤镜类型：normal/bitter
    currentEffect: '', // 当前选中的苦瓜脸特效
    currentFilter: 'normal', // 当前选中的普通滤镜
    sliderValue: 0, // 当前滑块的值
    serverUrl: 'http://192.168.1.101:5000',  // 已替换为本机局域网 IPv4
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
    filterStyles: {}, // 滤镜预览样式 (CSS filter)
    originalImagePath: '', // 保存原始图片路径
    maxImageSize: 5 * 1024 * 1024 // 5MB
  },

  onLoad(options) {
    if (options.image) {
      this.setData({
        imagePath: options.image,
        originalImagePath: options.image
      });
      
      // 检查图片大小
      this.checkAndCompressImage(options.image);
      
      // 生成滤镜预览样式
      this.generateFilterPreviews();
    }
  },

  // 生成滤镜预览样式 
  generateFilterPreviews() {
    if (!this.data.originalImagePath) return;
    
    const filterStyles = {
      grayscale: 'grayscale(50%)',
      sepia: 'sepia(50%)',
      brightness: 'brightness(150%)',
      contrast: 'contrast(150%)'
    };
    
    this.setData({
      filterStyles
    });
  },

  getCurrentFilterName() {
    const { filters, currentFilter } = this.data;
    const filter = filters.find(f => f.id === currentFilter);
    return filter ? filter.name : '';
  },

  // 切换滤镜类型
  switchFilterType(e) {
    const type = e.currentTarget.dataset.type;
    if(type === this.data.filterType) return;
    
    this.setData({ 
      filterType: type,
      currentEffect: '',
      currentFilter: 'normal'
    });
    
    // 切换到普通滤镜时生成预览图
    if (type === 'normal') {
      this.generateFilterPreviews();
    }
  },

  // 选择滤镜
  selectFilter(e) {
    const id = e.currentTarget.dataset.id;
    
    // 如果选择的滤镜当前值为0，设置为50作为默认值
    if (id !== 'normal' && this.data.filterValues[id] === 0) {
      const filterValues = {...this.data.filterValues};
      filterValues[id] = 50;
      this.setData({
        currentFilter: id,
        filterValues,
        sliderValue: 50
      }, () => {
        this.updateFilterStyle();
      });
    } else {
      this.setData({
        currentFilter: id,
        sliderValue: this.data.filterValues[id] || 0
      }, () => {
        this.updateFilterStyle();
      });
    }
  },

  // 滑块变化事件处理（带节流）
  onSliderChange: (function() {
    let timer = null;
    let pendingValue = null;
    
    return function(e) {
      const value = e.detail.value;
      const filter = this.data.currentFilter;
      
      if (filter === 'normal') return;
      
      // 保存待处理的值
      pendingValue = value;
      
      // 立即更新sliderValue，保证UI响应
      this.setData({ 
        sliderValue: value
      });
      
      // 使用节流更新filterValues和filterStyle
      if (timer) return;
      
      timer = setTimeout(() => {
        if (pendingValue !== null) {
          const filterValues = {...this.data.filterValues};
          filterValues[filter] = pendingValue;
          
          this.setData({ 
            filterValues
          }, () => {
            this.updateFilterStyle();
          });
          
          pendingValue = null;
        }
        timer = null;
      }, 50);  // 50ms节流
    };
  })(),

  // 更新滤镜样式
  updateFilterStyle() {
    const { filterValues, currentFilter } = this.data;
    let filterStyle = '';
    
    if (currentFilter !== 'normal') {
      switch(currentFilter) {
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
    
    // 只有当filterStyle真正改变时才更新
    if (this.data.filterStyle !== filterStyle) {
      this.setData({ filterStyle });
    }
  },

  // 选择苦瓜脸特效
  async selectEffect(e) {
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
    
    try {
      wx.showLoading({ title: '处理中...' });
      
      // 将图片转为base64
      const base64Image = await this.readFileAsBase64(this.data.originalImagePath);
      
      // 调用后端API应用特效
      const resultImage = await this.applyEffectApi(base64Image, effect);
      
      // 保存处理后的图片
      const tempFilePath = await this.saveImageFile(resultImage);
      
      // 更新显示
      this.setData({ imagePath: tempFilePath });
      
    } catch (err) {
      console.error('处理失败:', err);
      wx.showToast({
        title: err.message || '处理失败',
        icon: 'none'
      });
    } finally {
      wx.hideLoading();
    }
  },

  // 读取文件为base64
  readFileAsBase64(filePath) {
    return new Promise((resolve, reject) => {
      wx.getFileSystemManager().readFile({
        filePath: filePath,
        encoding: 'base64',
        success: (res) => resolve(res.data),
        fail: (err) => {
          console.error('读取图片失败:', err);
          reject(new Error('图片读取失败'));
        }
      });
    });
  },

  // 调用特效API
  applyEffectApi(base64Image, effect) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${this.data.serverUrl}/apply_filter`,
        method: 'POST',
        data: {
          image: base64Image,
          style: effect,
          intensity: 1.0
        },
        success: (res) => {
          if (res.data && res.data.image) {
            resolve(res.data.image);
          } else {
            reject(new Error('服务器返回数据格式错误'));
          }
        },
        fail: (err) => {
          console.error('请求失败:', err);
          reject(new Error('网络请求失败'));
        }
      });
    });
  },

  // 保存图片文件
  saveImageFile(base64Image) {
    return new Promise((resolve, reject) => {
      const buffer = wx.base64ToArrayBuffer(base64Image);
      const tempFilePath = `${wx.env.USER_DATA_PATH}/temp_${Date.now()}.jpg`;
      
      wx.getFileSystemManager().writeFile({
        filePath: tempFilePath,
        data: buffer,
        encoding: 'binary',
        success: () => resolve(tempFilePath),
        fail: (err) => {
          console.error('保存图片失败:', err);
          reject(new Error('图片保存失败'));
        }
      });
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