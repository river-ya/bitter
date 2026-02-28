function readFileAsBase64(filePath) {
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
}

function saveImageFile(base64Image, prefix = 'temp') {
  return new Promise((resolve, reject) => {
    const buffer = wx.base64ToArrayBuffer(base64Image);
    const tempFilePath = `${wx.env.USER_DATA_PATH}/${prefix}_${Date.now()}.jpg`;
    
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
}

function saveBase64ToTempFile(base64Data) {
  return new Promise((resolve, reject) => {
    const base64 = base64Data.replace(/^data:image\/\w+;base64,/, '');
    const buffer = wx.base64ToArrayBuffer(base64);
    const tempFilePath = `${wx.env.USER_DATA_PATH}/effect_${Date.now()}.jpg`;
    
    wx.getFileSystemManager().writeFile({
      filePath: tempFilePath,
      data: buffer,
      encoding: 'binary',
      success: () => resolve(tempFilePath),
      fail: (err) => {
        console.error('保存特效图片失败:', err);
        reject(err);
      }
    });
  });
}

module.exports = {
  readFileAsBase64,
  saveImageFile,
  saveBase64ToTempFile
};