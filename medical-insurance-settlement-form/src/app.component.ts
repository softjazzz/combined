
import { Component, signal, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

interface DiagnosisRow {
  id: number;
  name: string;
  code: string;
  opName: string;
  opCode: string;
}

interface InpatientDiagnosisRow {
  id: number;
  westDx: string;
  westCode: string;
  admCond: string;
  tcmDx: string;
  tcmCode: string;
  admCondTcm: string;
}

interface SurgeryRow {
  id: number;
  name: string;
  code: string;
  date: string;
  anesthesia: string;
  docName: string;
  docCode: string;
  anesName: string;
  anesCode: string;
}

interface IcuRow {
  id: number;
  type: string;
  inTime: string;
  outTime: string;
  total: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AppComponent {
  // Section 2: Outpatient Diagnosis
  diagnosisRows = signal<DiagnosisRow[]>(
    Array.from({ length: 6 }).map((_, i) => ({
      id: i, name: '', code: '', opName: '', opCode: ''
    }))
  );

  // Section 3: Inpatient Diagnosis (8 rows total to match image)
  inpatientDxRows = signal<InpatientDiagnosisRow[]>(
    Array.from({ length: 8 }).map((_, i) => ({
      id: i, westDx: '', westCode: '', admCond: '', tcmDx: '', tcmCode: '', admCondTcm: ''
    }))
  );

  // Section 3: Surgery Operations (8 rows)
  surgeryRows = signal<SurgeryRow[]>(
    Array.from({ length: 8 }).map((_, i) => ({
      id: i, name: '', code: '', date: '', anesthesia: '', docName: '', docCode: '', anesName: '', anesCode: ''
    }))
  );

  // Section 3: ICU (4 rows)
  icuRows = signal<IcuRow[]>(
    Array.from({ length: 4 }).map((_, i) => ({
      id: i, type: '', inTime: '', outTime: '', total: ''
    }))
  );

  // Section 4: Fees
  feeItems = [
    '床位费', '诊察费', '检查费', '化验费', '治疗费', '手术费', '护理费',
    '卫生材料费', '西药费', '中药饮片费', '中成药费', '一般诊疗费', '挂号费', '其他费'
  ];

  fundPayItems = [
    '医保统筹基金支付', '其他支付', '大病保险', '医疗救助', 
    '公务员医疗补助', '大额补充', '企业补充', '', ''
  ];

  printForm() {
    window.print();
  }
}
