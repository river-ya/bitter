Page({
  data: {
    tempImagePath: '', // 存储拍照后的临时图片路径
    devicePosition: 'back', // 摄像头方向
    cameraContext: null, // 添加相机上下文
    cameraAuthorized: false, // 添加相机授权状态
    currentImage: '',
    imageLoaded: false,
    filterIntensity: 50,
    serverUrl: 'http://192.168.1.101:5000',  // 已替换为本机局域网 IPv4
    showBitterFaceOptions: false,  // 控制苦瓜脸选项的显示
    currentStyle: 'style0', // 当前选中的特效样式
    previewImage: '',
    frameListener: null,
    effectFrame: '',
    lastFrameTime: 0, // 添加上一帧处理时间记录
    styles: [
      {
        id: 'style0',
        name: '原图',
        preview:'/images/original.png'
      },
      {
        id: 'style1',
        name: '苦瓜脸1',
        preview: '/images/effect1.png'  // 替换为实际的预览图路径
      },
      {
        id: 'style2',
        name: '苦瓜脸2',
        preview: '/images/effect2.png'
      },
      {
        id: 'style3',
        name: '苦瓜脸3',
        preview: '/images/effect3.png'
      }
    ],
  },

  onLoad() {
    this.checkCameraAuth();
  },

  checkCameraAuth() {
    wx.getSetting({
      success: (res) => {
        if (!res.authSetting['scope.camera']) {
          // 未授权，提示用户授权
          wx.authorize({
            scope: 'scope.camera',
            success: () => {
              console.log('相机权限授权成功');
              // 授权成功后启动相机
              this.startCamera();
            },
            fail: () => {
              console.error('相机权限授权失败');
              wx.showModal({
                title: '提示',
                content: '请授权使用相机功能',
                showCancel: false,
                success: (res) => {
                  if (res.confirm) {
                    wx.openSetting({
                      success: (res) => {
                        if (res.authSetting['scope.camera']) {
                          console.log('相机权限授权成功');
                          // 授权成功后启动相机
                          this.startCamera();
                        }
                      }
                    });
                  }
                }
              });
            }
          });
        } else {
          // 已授权，直接启动相机
          this.startCamera();
        }
      },
      fail: (err) => {
        console.error('获取设置失败:', err);
      }
    });
  },

  startCamera() {
    const camera = wx.createCameraContext();
    const listener = camera.onCameraFrame((frame) => {
      this.handleFrame(frame);
    });
    listener.start();
    this.setData({ frameListener: listener });
    console.log('相机帧监听器已启动');
  },

  // 关闭相机
  stopCamera() {
    // 关闭摄像头
    if (this.data.cameraContext) {
      this.setData({ cameraContext: null });
      console.log('相机已停止');
    }
    // 停止帧监听器
    if (this.data.frameListener) {
      this.data.frameListener.stop();
      this.setData({ frameListener: null });
      console.log('相机帧监听器已停止');
    }
  },

  // 翻转相机
  switchCamera() {
    this.setData({
      devicePosition: this.data.devicePosition === 'front' ? 'back' : 'front'
    });
  },

  // 处理实时视频帧
  handleFrame(frame) {
    if (!this.data.currentStyle) return;

    const now = Date.now();
    if (now - this.data.lastFrameTime < 100) {
      return;
    }
    
    this.setData({
      lastFrameTime: now
    });

    if (!frame.data || frame.data.length === 0) {
      console.error('无效的 frame.data:', frame.data);
      return;
    }

    // 创建离屏 canvas
    const canvas = wx.createOffscreenCanvas({
      type: '2d',
      width: frame.width,
      height: frame.height
    });
    const ctx = canvas.getContext('2d');

    // 创建图像数据对象
    const imageData = ctx.createImageData(frame.width, frame.height);
    imageData.data.set(new Uint8ClampedArray(frame.data));

    // 将图像数据绘制到canvas
    ctx.putImageData(imageData, 0, 0);

    // 直接将canvas内容转换为base64格式的JPEG图像
    try {
      const base64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
      
      // 发送到服务器处理
      wx.request({
        url: `${this.data.serverUrl}/apply_filter`,
        method: 'POST',
        data: {
          image: base64,
          style: this.data.currentStyle,
          intensity: 1.0,
        },
        success: (res) => {
          if (res.data.image) {
            this.setData({
              effectFrame: `data:image/jpeg;base64,${res.data.image}`
            });
          }
        },
        fail: (err) => {
          console.error('处理帧失败:', err);
        }
      });
    } catch (err) {
      console.error('转换图像失败:', err);
    }
  },

  // 拍照
  takePhoto() {
    wx.showLoading({
      title: '处理中...',
    });

    if (!this.data.cameraContext) {
      this.data.cameraContext = wx.createCameraContext();
    }

    this.data.cameraContext.takePhoto({
      quality: 'high',
      success: (res) => {
        this.setData({
          tempImagePath: res.tempImagePath,
          previewImage: res.tempImagePath,
        });
        wx.hideLoading();
      },
      fail: this.handleError
    });
    this.stopCamera();
  },
  retakePhoto() {
    this.startCamera();
    this.setData({
      tempImagePath: '',
      previewImage: '',
      effectFrame: '',
    });
  },

  savePhoto() {
    const imagePath = this.data.tempImagePath;
    
    if (!imagePath) {
      wx.showToast({
        title: '没有可保存的图片',
        icon: 'none'
      });
      return;
    }
    
    wx.showLoading({
      title: '保存中...'
    });
    
    wx.saveImageToPhotosAlbum({
      filePath: imagePath,
      success: () => {
        wx.hideLoading();
        wx.showToast({
          title: '保存成功',
          icon: 'success'
        });
        // 保存成功后返回拍照状态
        this.retakePhoto();
      },
      
      fail: (err) => {
        wx.hideLoading();
        console.error('保存失败：', err);
        wx.showToast({
          title: '保存失败',
          icon: 'none'
        });
        
        // 如果是因为用户未授权，则提示授权
        if (err.errMsg.indexOf('auth deny') !== -1) {
          wx.showModal({
            title: '提示',
            content: '需要相册权限才能保存图片',
            success: (res) => {
              if (res.confirm) {
                wx.openSetting();
              }
            }
          });
        }
      }
    });
  },

  // 选择特效样式
  selectStyle(e) {
    const style = e.currentTarget.dataset.style;
    // 如果点击当前已选中的特效，则取消选择
    if (style === 'style0')
      this.setData({ effectFrame: '', });
    // if (this.data.currentStyle === style) {
      // this.setData({ 
        // effectFrame: '',  // 清除特效
        // currentStyle: '',
      // });
    // }
    // else {
    this.setData({ currentStyle: style });
    // }
    console.log('选择特效:', style);
  },

  handleError(err) {
    wx.hideLoading();
    console.error(err);
    wx.showToast({
      title: '操作失败',
      icon: 'none'
    });
  },
}); 