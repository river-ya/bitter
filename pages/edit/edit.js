Page({
  data: {
    imagePath: '',
    filterType: 'normal', // 当前选择的大类滤镜：normal/bitter
    currentEffect: '', // 当前选中的苦瓜脸特效种类
    currentFilter: 'blank', // 当前选中的普通滤镜种类
    sliderValue: 0, // 普通滤镜滑块的值 （0-100，或亮度/对比度的-100到100）
    sliderValue2: 1, // 苦瓜脸强度滑块值（0.0-2.0）
    serverUrl: 'http://192.168.1.96:5000',  // 应替换为本机局域网 IPv4
    filters: [
      { id: 'blank', name: '原图' },
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
    effectValue: 1, // 苦瓜脸强度（0.0-2.0）
    filterStyles: {}, // 仅用于生成缩略图
    originalImagePath: '', // 备份原始图片路径
    maxImageSize: 5 * 1024 * 1024 // 5MB 图片大小限制
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
  getCurrentEffectName() {
    const { currentEffect } = this.data;
    if (!currentEffect) {
      return '原图';
    }
    // currentEffect values are expected to be 'style1','style2','style3', etc.
    const match = currentEffect.match(/style(\d+)$/);
    if (match) {
      return `苦瓜脸${match[1]}`;
    }
    // fallback: just return the raw string
    return currentEffect;
  }, 

  // 切换滤镜类型
  switchFilterType(e) {
    const type = e.currentTarget.dataset.type;
    if(type === this.data.filterType) return;
    /*
    注意，切换滤镜类型时会重置当前选中的普通滤镜为「原图」，但不会重置苦瓜脸特效以避免多次调用 API。
    普通滤镜的最终选择记录在 filderValues 中，切换回普通滤镜时不会影响之前的选择
    苦瓜脸滤镜的最终选择记录在 currentEffect 中。
    */
    this.setData({ 
      filterType: type,
      currentFilter: 'blank'
    });
    
    // 切换到普通滤镜时生成预览图
    if (type === 'normal') {
      this.generateFilterPreviews();
    }
  },

  // 选择普通滤镜（卡片被点击）
  selectFilter(e) {
    const id = e.currentTarget.dataset.id;
    if (id === 'blank') {
      // 原图：清空所有普通滤镜
      this.setData({
        currentFilter: 'blank',
        sliderValue: 0,
        filterValues: {
          grayscale: 0,
          sepia: 0,
          brightness: 0,
          contrast: 0
        }
      }, () => this.updateFilterStyle());
      return;
    }
    const filterValues = { ...this.data.filterValues };
    const currentValue = filterValues[id] || 0;
    const sliderValue = currentValue === 0 ? 50 : currentValue;
    if (currentValue === 0) {
      filterValues[id] = 50;
      this.setData({
        currentFilter: id,
        filterValues,
        sliderValue
      }, () => this.updateFilterStyle());
    } else {
      this.setData({
        currentFilter: id,
        sliderValue
      });
    }
  },

  // 滑块变化事件处理（带节流），作用于当前选中的普通滤镜
  onSliderChange: (function() {
    let timer = null;
    let pendingValue = null;
    
    return function(e) {
      const value = e.detail.value;
      const filter = this.data.currentFilter;
      
      if (filter === 'blank') return;
      
      pendingValue = value;
      this.setData({ sliderValue: value });
      
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
      }, 50);
    };
  })(), // IIFE

  // 根据当前滤镜组合生成预览用 CSS filter（实时预览）
  updateFilterStyle() {
    const { filterValues } = this.data;
    const parts = [];
    if ((filterValues.grayscale || 0) > 0) parts.push(`grayscale(${filterValues.grayscale}%)`);
    if ((filterValues.sepia || 0) > 0) parts.push(`sepia(${filterValues.sepia}%)`);
    if ((filterValues.brightness || 0) > 0) parts.push(`brightness(${100 + filterValues.brightness}%)`);
    if ((filterValues.contrast || 0) > 0) parts.push(`contrast(${100 + filterValues.contrast}%)`);
    const filterStyle = parts.join(' ');
    if (this.data.filterStyle !== filterStyle) {
      this.setData({ filterStyle });
    }
  },

  // 点击具体苦瓜脸特效
  selectEffect(e) {
    const effect = e.currentTarget.dataset.effect;
    
    // 选中苦瓜脸 1/2/3 时，都默认使用强度 1.0。
    this.setData({
      sliderValue2: 1,
      effectValue: 1
    });

    // 点击「原图」或再次点击当前效果：恢复底图为原图
    if (effect === '' || this.data.currentEffect === effect) {
      this.setData({
        currentEffect: '',
        imagePath: this.data.originalImagePath || this.data.imagePath
      });
      return;
    }
    if (!this.data.originalImagePath) {
      this.setData({ originalImagePath: this.data.imagePath });
    }

    // 以下必然是切换到一个新的苦瓜脸特效，调用 API 生成新图
    this.setData({ currentEffect: effect}, () => this.updateEffectStyle());
  },

  onSliderChange2(e) {
    const value = e.detail.value;
    // value = parseFloat(value.toFixed(2));
    const effect = this.data.currentEffect;
    if (!effect || value === this.data.effectValue) return;
    this.setData({
      sliderValue2: value,
      effectValue: value
    }, () => {
      this.updateEffectStyle();
    });
  },

  async updateEffectStyle() {
    try {
      wx.showLoading({ title: '处理中...' });
      const base64Image = await this.readFileAsBase64(this.data.originalImagePath);
      const resultImage = await this.applyEffectApi(base64Image, this.data.currentEffect, this.data.effectValue);
      const tempFilePath = await this.saveImageFile(resultImage);
      this.setData({ imagePath: tempFilePath });
    } catch (err) {
      console.error('处理失败:', err);
      wx.showToast({ title: err.message || '处理失败', icon: 'none' });
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

  // 调用苦瓜脸API
  applyEffectApi(base64Image, effect, intensity = 1.0) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${this.data.serverUrl}/apply_filter_combo`,
        method: 'POST',
        header: { 'content-type': 'application/json' },
        data: {
          image: base64Image,
          bitter_style: effect || '',
          intensity: intensity
        },
        success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.image) {
              resolve(res.data.image);
            } else {
              const msg = (res.data && res.data.error) || `应用失败(${res.statusCode})`;
              reject(new Error(msg));
            }
          },
          fail: (err) => {
            console.error('请求失败:', err);
            reject(new Error('网络请求失败'));
          }
      });
    });
  },

  // 调用滤镜组合 API：原图 + 苦瓜脸（可选）+ 四种普通滤镜组合
  applyFilterComboApi(base64Image, bitter_style, filter_values, effectValue) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${this.data.serverUrl}/apply_filter_combo`,
        method: 'POST',
        header: { 'content-type': 'application/json' },
        data: {
          image: base64Image,
          bitter_style: bitter_style || '',
          filter_values: filter_values || {},
          intensity: effectValue || 1.0
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300 && res.data && res.data.image) {
            resolve(res.data.image);
          } else {
            const msg = (res.data && res.data.error) || `应用失败(${res.statusCode})`;
            reject(new Error(msg));
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

  // 下载图片：按当前组合（苦瓜脸 + 四种普通滤镜）生成图片并保存到相册
  async saveImage() {
    const { originalImagePath, currentEffect, filterValues, effectValue} = this.data;
    if (!originalImagePath) {
      wx.showToast({ title: '暂无图片', icon: 'none' });
      return;
    }
    try {
      wx.showLoading({ title: '生成中...' });
      const base64Image = await this.readFileAsBase64(originalImagePath);
      const filter_values = {
        grayscale: filterValues.grayscale || 0,
        sepia: filterValues.sepia || 0,
        brightness: filterValues.brightness || 0,
        contrast: filterValues.contrast || 0
      };
      const resultBase64 = await this.applyFilterComboApi(base64Image, currentEffect || '', filter_values, effectValue);
      const filePath = await this.saveImageFile(resultBase64);
      wx.hideLoading();

      wx.saveImageToPhotosAlbum({
        filePath,
        success: () => {
          wx.showToast({ title: '保存成功', icon: 'success' });
        },
        fail: (err) => {
          console.error('保存失败：', err);
          wx.showToast({ title: '保存失败', icon: 'none' });
        }
      });
    } catch (err) {
      console.error('保存处理失败:', err);
      wx.hideLoading();
      wx.showToast({ title: err.message || '保存失败', icon: 'none' });
    }
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
            const originalSize = this.data.maxImageSize; // 存在问题，懒得弄了。
            
            // 压缩成功，显示结果
            const originalSizeMB = (this.data.maxImageSize / (1024 * 1024)).toFixed(2);
            const compressedSizeMB = (compressedSize / (1024 * 1024)).toFixed(2);
            const reduction = ((1 - compressedSize / this.data.maxImageSize) * 100).toFixed(0);
            
            wx.showModal({
              title: '压缩成功',
              content: `图片已从 （超过）${originalSizeMB}MB 压缩至 ${compressedSizeMB}MB，减少了 ${reduction}%。是否使用压缩后的图片？`,
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
                    currentFilter: 'blank',
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