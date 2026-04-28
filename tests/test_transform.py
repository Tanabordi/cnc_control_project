import unittest
import math
from core.transform import compute_affine_2point, apply_affine_to_point

class TestTransformMath(unittest.TestCase):
    def test_basic_rotation_and_translation(self):
        # สมมติพิกัดในไฟล์งาน (CSV/Vector)
        p1_design = (0.0, 0.0)
        p2_design = (10.0, 0.0)  
        
        # สมมติว่าวางแผ่นงานเอียง 90 องศาบนเครื่อง CNC และเลื่อนไปอยู่ที่ X=100, Y=100
        p1_machine = (100.0, 100.0)
        p2_machine = (100.0, 110.0) 
        
        # 1. รับค่าเป็น Object ชื่อ result
        result = compute_affine_2point(p1_design, p2_design, p1_machine, p2_machine)
        
        # ดึงค่าออกมาจาก Object (อิงจากชื่อตัวแปรที่เจอบ่อย ถ้า Error ให้เช็กชื่อใน core/transform.py)
        scale = result.scale
        rot = getattr(result, 'rotation', getattr(result, 'rot', 0))
        tx = getattr(result, 'tx', getattr(result, 'offset_x', 0))
        ty = getattr(result, 'ty', getattr(result, 'offset_y', 0))
        
        # สเกลต้องเท่าเดิม (1.0) และมุมต้องเป็น 90 องศา (pi/2)
        self.assertAlmostEqual(scale, 1.0, places=3)
        self.assertAlmostEqual(rot, math.pi / 2, places=3)
        
        # 2. ทดสอบนำค่าไปคำนวณจุดใหม่
        test_pt = (5.0, 0.0)
        
        res_x, res_y = apply_affine_to_point(
            test_pt[0], test_pt[1],
            anchor=p1_design,
            cos_r=result.cos_r,
            sin_r=result.sin_r,
            translation=p1_machine
        )
        
        # จุดใหม่บนเครื่องต้องโดนหมุนและย้ายไปอยู่ที่ (100.0, 105.0)
        self.assertAlmostEqual(res_x, 100.0, places=3)
        self.assertAlmostEqual(res_y, 105.0, places=3)

if __name__ == '__main__':
    unittest.main()
