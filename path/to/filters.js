// 只保留苦瓜脸滤镜定义
const filters = {
  bitterGourd: {
    name: '苦瓜脸',
    filter: (face) => {
      // 苦瓜脸变形逻辑
      face.scale(1, 1.2);  // 垂直拉伸
      face.rotate(10);     // 稍微倾斜
      // 其他苦瓜脸相关的变形效果...
    }
  }
};

// 更新滤镜选择逻辑
function applyFilter(selectedFilter, faceElement) {
  const filter = filters[selectedFilter];
  if (filter) {
    filter.filter(faceElement);
  }
} 