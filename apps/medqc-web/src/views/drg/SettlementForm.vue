<template>
  <div class="settlement-form">
    <!-- Page Header -->
    <a-page-header
      title="医保结算清单"
      sub-title="Medical Insurance Settlement Form"
      @back="() => $router.back()"
      class="page-header"
    >
      <template #extra>
        <a-space>
          <a-button @click="handleValidate">
            <template #icon><CheckCircleOutlined /></template>
            质控校验
          </a-button>
          <a-button @click="handlePrint">
            <template #icon><PrinterOutlined /></template>
            打印
          </a-button>
          <a-button type="primary" @click="handleSave" :loading="saving">
            <template #icon><SaveOutlined /></template>
            保存
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-row :gutter="16">
        <!-- Left: Form -->
        <a-col :span="qcVisible ? 18 : 24">
          <div class="form-container">
            <!-- Title -->
            <div class="form-title">
              <a-input v-model:value="form.basicInfo.insuredArea" placeholder="地区" class="region-input" />
              <span class="title-text">医疗保障基金结算清单</span>
            </div>

            <!-- Top Header Fields -->
            <div class="header-fields">
              <a-row :gutter="16">
                <a-col :span="12"></a-col>
                <a-col :span="12" class="text-right">
                  <span class="field-label">清单流水号</span>
                  <a-input v-model:value="form.basicInfo.serialNumber" class="inline-input w-40" />
                </a-col>
              </a-row>
              <a-row :gutter="16" class="mt-2">
                <a-col :span="12">
                  <span class="field-label">定点医疗机构名称</span>
                  <a-input v-model:value="form.basicInfo.institutionName" class="inline-input flex-1" />
                </a-col>
                <a-col :span="12" class="text-right">
                  <span class="field-label">定点医疗机构代码</span>
                  <a-input v-model:value="form.basicInfo.institutionCode" class="inline-input w-48" />
                </a-col>
              </a-row>
              <a-row :gutter="16" class="mt-2">
                <a-col :span="8">
                  <span class="field-label">医保编号</span>
                  <a-input v-model:value="form.basicInfo.insuranceNumber" class="inline-input" />
                </a-col>
                <a-col :span="8">
                  <span class="field-label">病案号</span>
                  <a-input v-model:value="form.basicInfo.caseNumber" class="inline-input" />
                </a-col>
                <a-col :span="8" class="text-right">
                  <span class="field-label">医保结算等级</span>
                  <a-input v-model:value="form.basicInfo.settlementLevel" class="inline-input w-24" />
                </a-col>
              </a-row>
            </div>

            <!-- Section 1: Basic Information -->
            <div class="form-section">
              <div class="section-header">一、基本信息</div>
              <div class="section-body">
                <!-- Row 1: Name, Gender, Birth, Age -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="4">
                    <span class="field-label">姓名</span>
                    <a-input v-model:value="form.basicInfo.patientName" size="small" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">性别</span>
                    <a-radio-group v-model:value="form.basicInfo.gender" size="small">
                      <a-radio :value="1">男</a-radio>
                      <a-radio :value="2">女</a-radio>
                    </a-radio-group>
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">出生日期</span>
                    <a-date-picker v-model:value="birthDate" size="small" class="w-full" />
                  </a-col>
                  <a-col :span="3">
                    <span class="field-label">年龄</span>
                    <a-input-number v-model:value="form.basicInfo.age" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="5">
                    <span class="field-label">国籍</span>
                    <a-input v-model:value="form.basicInfo.nationality" size="small" />
                  </a-col>
                </a-row>

                <!-- Row 2: Age in days, Ethnicity, ID Type, ID Number -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="5">
                    <span class="field-label">不足1岁年龄(天)</span>
                    <a-input-number v-model:value="form.basicInfo.ageInDays" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">民族</span>
                    <a-input v-model:value="form.basicInfo.ethnicity" size="small" />
                  </a-col>
                  <a-col :span="5">
                    <span class="field-label">证件类别</span>
                    <a-select v-model:value="form.basicInfo.idCardType" size="small" class="w-full">
                      <a-select-option value="01">居民身份证</a-select-option>
                      <a-select-option value="02">护照</a-select-option>
                      <a-select-option value="03">军官证</a-select-option>
                      <a-select-option value="99">其他</a-select-option>
                    </a-select>
                  </a-col>
                  <a-col :span="10">
                    <span class="field-label">证件号码</span>
                    <a-input v-model:value="form.basicInfo.idCardNumber" size="small" />
                  </a-col>
                </a-row>

                <!-- Row 3: Occupation, Address -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="4">
                    <span class="field-label">职业</span>
                    <a-input v-model:value="form.basicInfo.occupation" size="small" />
                  </a-col>
                  <a-col :span="20">
                    <span class="field-label">现住址</span>
                    <a-input-group compact>
                      <a-input v-model:value="form.basicInfo.currentAddress.province" size="small" placeholder="省" style="width: 20%" />
                      <a-input v-model:value="form.basicInfo.currentAddress.city" size="small" placeholder="市" style="width: 20%" />
                      <a-input v-model:value="form.basicInfo.currentAddress.county" size="small" placeholder="县" style="width: 20%" />
                      <a-input v-model:value="form.basicInfo.currentAddress.detail" size="small" placeholder="详细地址" style="width: 40%" />
                    </a-input-group>
                  </a-col>
                </a-row>

                <!-- Row 4: Work info -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">工作单位名称</span>
                    <a-input v-model:value="form.basicInfo.workUnit" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">工作单位地址</span>
                    <a-input v-model:value="form.basicInfo.workAddress" size="small" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">单位电话</span>
                    <a-input v-model:value="form.basicInfo.workPhone" size="small" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">邮编</span>
                    <a-input v-model:value="form.basicInfo.workPostcode" size="small" />
                  </a-col>
                </a-row>

                <!-- Row 5: Contact info -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="4">
                    <span class="field-label">联系人姓名</span>
                    <a-input v-model:value="form.basicInfo.contactName" size="small" />
                  </a-col>
                  <a-col :span="3">
                    <span class="field-label">关系</span>
                    <a-input v-model:value="form.basicInfo.contactRelation" size="small" />
                  </a-col>
                  <a-col :span="13">
                    <span class="field-label">地址</span>
                    <a-input-group compact>
                      <a-input v-model:value="form.basicInfo.contactAddress.province" size="small" placeholder="省" style="width: 20%" />
                      <a-input v-model:value="form.basicInfo.contactAddress.city" size="small" placeholder="市" style="width: 20%" />
                      <a-input v-model:value="form.basicInfo.contactAddress.county" size="small" placeholder="县" style="width: 20%" />
                      <a-input v-model:value="form.basicInfo.contactAddress.detail" size="small" placeholder="详细地址" style="width: 40%" />
                    </a-input-group>
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">电话</span>
                    <a-input v-model:value="form.basicInfo.contactPhone" size="small" />
                  </a-col>
                </a-row>

                <!-- Row 6: Insurance info -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">医保类型</span>
                    <a-select v-model:value="form.basicInfo.insuranceType" size="small" class="w-full">
                      <a-select-option value="310">城镇职工基本医疗保险</a-select-option>
                      <a-select-option value="320">城乡居民基本医疗保险</a-select-option>
                      <a-select-option value="330">离休人员医疗</a-select-option>
                      <a-select-option value="390">其他</a-select-option>
                    </a-select>
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">特殊人员类型</span>
                    <a-input v-model:value="form.basicInfo.specialPersonType" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">参保地</span>
                    <a-input v-model:value="form.basicInfo.insuredArea" size="small" />
                  </a-col>
                </a-row>

                <!-- Row 7: Newborn info -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">新生儿入院类型</span>
                    <a-select v-model:value="form.basicInfo.newbornAdmissionType" size="small" class="w-full" allow-clear>
                      <a-select-option value="1">正常新生儿</a-select-option>
                      <a-select-option value="2">患病新生儿</a-select-option>
                    </a-select>
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">新生儿出生体重(克)</span>
                    <a-input-number v-model:value="form.basicInfo.newbornBirthWeight" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">新生儿入院体重(克)</span>
                    <a-input-number v-model:value="form.basicInfo.newbornAdmissionWeight" size="small" :min="0" class="w-full" />
                  </a-col>
                </a-row>
              </div>
            </div>

            <!-- Section 2: Outpatient Chronic Disease -->
            <div class="form-section">
              <div class="section-header">二、门诊慢特病诊疗信息</div>
              <div class="section-body">
                <a-row :gutter="16" class="form-row">
                  <a-col :span="12">
                    <span class="field-label">诊断科室</span>
                    <a-input v-model:value="form.outpatientInfo.department" size="small" />
                  </a-col>
                  <a-col :span="12">
                    <span class="field-label">就诊日期</span>
                    <a-date-picker v-model:value="outpatientVisitDate" size="small" class="w-full" />
                  </a-col>
                </a-row>

                <a-table
                  :columns="outpatientColumns"
                  :data-source="form.outpatientInfo.diagnosisRows"
                  :pagination="false"
                  size="small"
                  bordered
                  class="mt-2"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.dataIndex === 'diagnosisName'">
                      <a-input v-model:value="record.diagnosisName" size="small" />
                    </template>
                    <template v-else-if="column.dataIndex === 'diagnosisCode'">
                      <a-input v-model:value="record.diagnosisCode" size="small" />
                    </template>
                    <template v-else-if="column.dataIndex === 'procedureName'">
                      <a-input v-model:value="record.procedureName" size="small" />
                    </template>
                    <template v-else-if="column.dataIndex === 'procedureCode'">
                      <a-input v-model:value="record.procedureCode" size="small" />
                    </template>
                  </template>
                </a-table>
              </div>
            </div>

            <!-- Section 3: Inpatient Info -->
            <div class="form-section">
              <div class="section-header">三、住院诊疗信息</div>
              <div class="section-body">
                <!-- Hospitalization Type -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">住院医疗类型</span>
                    <a-radio-group v-model:value="inpatientData.hospitalizationType" size="small">
                      <a-radio :value="1">住院</a-radio>
                      <a-radio :value="2">日间手术</a-radio>
                    </a-radio-group>
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">入院途径</span>
                    <a-radio-group v-model:value="inpatientData.admissionRoute" size="small">
                      <a-radio :value="1">急诊</a-radio>
                      <a-radio :value="2">门诊</a-radio>
                      <a-radio :value="3">转入</a-radio>
                      <a-radio :value="9">其他</a-radio>
                    </a-radio-group>
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">治疗类别</span>
                    <a-radio-group v-model:value="inpatientData.treatmentCategory" size="small">
                      <a-radio :value="1">西医</a-radio>
                      <a-radio :value="2">中医</a-radio>
                      <a-radio :value="3">中西医</a-radio>
                    </a-radio-group>
                  </a-col>
                </a-row>

                <a-divider style="margin: 8px 0" />

                <!-- Admission/Discharge Time -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">入院时间</span>
                    <a-date-picker v-model:value="admissionTime" show-time size="small" class="w-full" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">入院科别</span>
                    <a-input v-model:value="inpatientData.admissionDepartment" size="small" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">转科科别</span>
                    <a-input v-model:value="inpatientData.transferDepartment" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">出院时间</span>
                    <a-date-picker v-model:value="dischargeTime" show-time size="small" class="w-full" />
                  </a-col>
                </a-row>

                <a-row :gutter="8" class="form-row">
                  <a-col :span="4">
                    <span class="field-label">出院科别</span>
                    <a-input v-model:value="inpatientData.dischargeDepartment" size="small" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">实际住院天数</span>
                    <a-input-number v-model:value="inpatientData.actualLOS" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">门(急)诊诊断(西医)</span>
                    <a-input v-model:value="inpatientData.emergencyWestDiagnosis" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">门(急)诊诊断(中医)</span>
                    <a-input v-model:value="inpatientData.emergencyTCMDiagnosis" size="small" />
                  </a-col>
                </a-row>

                <a-divider style="margin: 8px 0" />

                <!-- Diagnosis Table -->
                <div class="sub-section-title">出院诊断</div>
                <a-table
                  :columns="diagnosisColumns"
                  :data-source="diagnosisRows"
                  :pagination="false"
                  size="small"
                  bordered
                  class="compact-table"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.dataIndex === 'rowLabel'">
                      <span class="row-label">{{ index === 0 ? '主要诊断' : '其他诊断' + index }}</span>
                    </template>
                    <template v-else>
                      <a-input v-model:value="record[column.dataIndex]" size="small" />
                    </template>
                  </template>
                </a-table>

                <a-divider style="margin: 8px 0" />

                <!-- Surgery Table -->
                <div class="sub-section-title">手术及操作</div>
                <a-table
                  :columns="surgeryColumns"
                  :data-source="surgeryRows"
                  :pagination="false"
                  size="small"
                  bordered
                  class="compact-table"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.dataIndex === 'rowLabel'">
                      <span class="row-label">{{ index === 0 ? '主要手术' : '其他手术' + index }}</span>
                    </template>
                    <template v-else>
                      <a-input v-model:value="record[column.dataIndex]" size="small" />
                    </template>
                  </template>
                </a-table>

                <a-divider style="margin: 8px 0" />

                <!-- Nursing and Discharge -->
                <a-row :gutter="8" class="form-row">
                  <a-col :span="4">
                    <span class="field-label">特级护理(天)</span>
                    <a-input-number v-model:value="inpatientData.specialNursingDays" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">一级护理(天)</span>
                    <a-input-number v-model:value="inpatientData.level1NursingDays" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">二级护理(天)</span>
                    <a-input-number v-model:value="inpatientData.level2NursingDays" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="4">
                    <span class="field-label">三级护理(天)</span>
                    <a-input-number v-model:value="inpatientData.level3NursingDays" size="small" :min="0" class="w-full" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">离院方式</span>
                    <a-select v-model:value="inpatientData.dischargeMethod" size="small" class="w-full">
                      <a-select-option :value="1">医嘱离院</a-select-option>
                      <a-select-option :value="2">医嘱转院</a-select-option>
                      <a-select-option :value="3">转社区</a-select-option>
                      <a-select-option :value="4">非医嘱离院</a-select-option>
                      <a-select-option :value="5">死亡</a-select-option>
                      <a-select-option :value="9">其他</a-select-option>
                    </a-select>
                  </a-col>
                </a-row>

                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">主诊医师姓名</span>
                    <a-input v-model:value="inpatientData.attendingPhysicianName" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">主诊医师代码</span>
                    <a-input v-model:value="inpatientData.attendingPhysicianCode" size="small" />
                  </a-col>
                </a-row>
              </div>
            </div>

            <!-- Section 4: Fee Info -->
            <div class="form-section">
              <div class="section-header">四、医疗收费信息</div>
              <div class="section-body">
                <a-row :gutter="8" class="form-row">
                  <a-col :span="8">
                    <span class="field-label">业务流水号</span>
                    <a-input v-model:value="feeData.businessSerialNumber" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">票据代码</span>
                    <a-input v-model:value="feeData.invoiceCode" size="small" />
                  </a-col>
                  <a-col :span="8">
                    <span class="field-label">票据号码</span>
                    <a-input v-model:value="feeData.invoiceNumber" size="small" />
                  </a-col>
                </a-row>

                <!-- Fee Items Table -->
                <div class="sub-section-title mt-2">费用明细</div>
                <a-table
                  :columns="feeColumns"
                  :data-source="feeItems"
                  :pagination="false"
                  size="small"
                  bordered
                  class="compact-table fee-table"
                >
                  <template #bodyCell="{ column, record }">
                    <template v-if="column.dataIndex === 'itemName'">
                      <span :class="{ 'font-bold': record.isCategory }">{{ record.itemName }}</span>
                    </template>
                    <template v-else-if="!record.isCategory">
                      <a-input-number v-model:value="record[column.dataIndex]" size="small" :min="0" :precision="2" class="w-full" />
                    </template>
                  </template>
                </a-table>

                <a-divider style="margin: 12px 0" />

                <!-- Payment Summary -->
                <a-row :gutter="16">
                  <a-col :span="12">
                    <div class="payment-card">
                      <div class="payment-title">基金支付</div>
                      <div class="payment-row" v-for="(item, idx) in fundPayItems" :key="idx">
                        <span>{{ item.name }}</span>
                        <a-input-number v-model:value="item.amount" size="small" :min="0" :precision="2" style="width: 120px" />
                      </div>
                    </div>
                  </a-col>
                  <a-col :span="12">
                    <div class="payment-card">
                      <div class="payment-title">个人支付</div>
                      <div class="payment-row">
                        <span>个人自付</span>
                        <a-input-number v-model:value="feeData.personalSelfPay" size="small" :min="0" :precision="2" style="width: 120px" />
                      </div>
                      <div class="payment-row">
                        <span>个人自费</span>
                        <a-input-number v-model:value="feeData.personalSelfExpense" size="small" :min="0" :precision="2" style="width: 120px" />
                      </div>
                      <div class="payment-row">
                        <span>个人账户支付</span>
                        <a-input-number v-model:value="feeData.personalAccountPay" size="small" :min="0" :precision="2" style="width: 120px" />
                      </div>
                      <div class="payment-row">
                        <span>个人现金支付</span>
                        <a-input-number v-model:value="feeData.personalCashPay" size="small" :min="0" :precision="2" style="width: 120px" />
                      </div>
                    </div>
                  </a-col>
                </a-row>

                <a-divider style="margin: 12px 0" />

                <!-- Payment Method -->
                <a-row class="form-row">
                  <a-col :span="24">
                    <span class="field-label">医保支付方式</span>
                    <a-checkbox-group v-model:value="feeData.paymentMethod">
                      <a-checkbox :value="1">按项目</a-checkbox>
                      <a-checkbox :value="2">单病种</a-checkbox>
                      <a-checkbox :value="3">按病种分值(DIP)</a-checkbox>
                      <a-checkbox :value="4">疾病诊断相关分组(DRG)</a-checkbox>
                      <a-checkbox :value="5">按床日</a-checkbox>
                      <a-checkbox :value="6">按人头</a-checkbox>
                    </a-checkbox-group>
                  </a-col>
                </a-row>
              </div>
            </div>

            <!-- Footer -->
            <div class="form-section">
              <div class="section-body">
                <a-row :gutter="16" class="form-row">
                  <a-col :span="6">
                    <span class="field-label">医疗机构填报部门</span>
                    <a-input v-model:value="form.reportingDepartment" size="small" />
                  </a-col>
                  <a-col :span="6">
                    <span class="field-label">医疗机构填报人</span>
                    <a-input v-model:value="form.reportingPerson" size="small" />
                  </a-col>
                  <a-col :span="6">
                    <span class="field-label">医保机构</span>
                    <a-input v-model:value="form.insuranceAgency" size="small" />
                  </a-col>
                  <a-col :span="6">
                    <span class="field-label">医保机构经办人</span>
                    <a-input v-model:value="form.insuranceAgent" size="small" />
                  </a-col>
                </a-row>
              </div>
            </div>

          </div>
        </a-col>

        <!-- Right: QC Panel -->
        <a-col v-if="qcVisible" :span="6">
          <div class="qc-panel">
            <div class="qc-header">
              <span>质控校验结果</span>
              <a-button type="text" size="small" @click="qcVisible = false">
                <CloseOutlined />
              </a-button>
            </div>
            <div class="qc-summary">
              <a-statistic title="错误" :value="qcReport.errorCount" :value-style="{ color: '#ff4d4f' }" />
              <a-statistic title="警告" :value="qcReport.warningCount" :value-style="{ color: '#faad14' }" />
            </div>
            <div class="qc-list">
              <div v-for="item in qcReport.results" :key="item.ruleId" class="qc-item" :class="item.severity">
                <span class="qc-rule">{{ item.ruleId }}</span>
                <span class="qc-field">{{ item.field }}</span>
                <span class="qc-message">{{ item.message }}</span>
              </div>
              <a-empty v-if="qcReport.results.length === 0" description="暂无校验问题" />
            </div>
          </div>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  SaveOutlined,
  PrinterOutlined,
  CheckCircleOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'
import type { SettlementForm, SettlementQCReport, OutpatientDiagnosisRow } from '@/types/settlement'

// Form data
const form = reactive<SettlementForm>({
  basicInfo: {
    institutionName: '',
    institutionCode: '',
    serialNumber: '',
    insuranceNumber: '',
    caseNumber: '',
    settlementLevel: '',
    reportDate: '',
    patientName: '',
    gender: null,
    birthDate: '',
    age: null,
    ageInDays: null,
    nationality: '中国',
    ethnicity: '汉族',
    idCardType: '01',
    idCardNumber: '',
    occupation: '',
    currentAddress: { province: '', city: '', county: '', detail: '' },
    workUnit: '',
    workAddress: '',
    workPhone: '',
    workPostcode: '',
    contactName: '',
    contactRelation: '',
    contactAddress: { province: '', city: '', county: '', detail: '' },
    contactPhone: '',
    insuranceType: '',
    specialPersonType: '',
    insuredArea: '',
    newbornAdmissionType: '',
    newbornBirthWeight: null,
    newbornAdmissionWeight: null
  },
  outpatientInfo: {
    department: '',
    visitDate: '',
    diagnosisRows: Array.from({ length: 3 }, (_, i) => ({
      id: i + 1,
      diagnosisName: '',
      diagnosisCode: '',
      procedureName: '',
      procedureCode: ''
    }))
  },
  inpatientInfo: {} as any,
  feeInfo: {} as any,
  reportingDepartment: '',
  reportingPerson: '',
  insuranceAgency: '',
  insuranceAgent: ''
})

// Date pickers
const birthDate = ref<Dayjs | null>(null)
const outpatientVisitDate = ref<Dayjs | null>(null)
const admissionTime = ref<Dayjs | null>(null)
const dischargeTime = ref<Dayjs | null>(null)

// Inpatient Data
const inpatientData = reactive({
  hospitalizationType: null as number | null,
  admissionRoute: null as number | null,
  treatmentCategory: null as number | null,
  admissionDepartment: '',
  transferDepartment: '',
  dischargeDepartment: '',
  actualLOS: null as number | null,
  emergencyWestDiagnosis: '',
  emergencyTCMDiagnosis: '',
  specialNursingDays: null as number | null,
  level1NursingDays: null as number | null,
  level2NursingDays: null as number | null,
  level3NursingDays: null as number | null,
  dischargeMethod: null as number | null,
  attendingPhysicianName: '',
  attendingPhysicianCode: ''
})

// Fee Data
const feeData = reactive({
  businessSerialNumber: '',
  invoiceCode: '',
  invoiceNumber: '',
  personalSelfPay: null as number | null,
  personalSelfExpense: null as number | null,
  personalAccountPay: null as number | null,
  personalCashPay: null as number | null,
  paymentMethod: [] as number[]
})

// Diagnosis Rows (Section 3)
const diagnosisRows = ref(Array.from({ length: 5 }, (_, i) => ({
  id: i + 1,
  westDiagnosis: '',
  westCode: '',
  admissionCondition: '',
  tcmDiagnosis: '',
  tcmCode: ''
})))

// Surgery Rows (Section 3)
const surgeryRows = ref(Array.from({ length: 3 }, (_, i) => ({
  id: i + 1,
  name: '',
  code: '',
  date: '',
  anesthesia: '',
  surgeonName: '',
  surgeonCode: ''
})))

// Fee Items (Section 4)
const feeItems = ref([
  { id: 1, itemName: '（一）综合医疗服务类', isCategory: true },
  { id: 2, itemName: '1.一般医疗服务费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 3, itemName: '2.一般治疗操作费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 4, itemName: '3.护理费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 5, itemName: '（二）诊断类', isCategory: true },
  { id: 6, itemName: '5.病理诊断费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 7, itemName: '6.实验室诊断费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 8, itemName: '7.影像学诊断费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 9, itemName: '（三）治疗类', isCategory: true },
  { id: 10, itemName: '11.手术治疗费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 11, itemName: '12.麻醉费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 12, itemName: '（四）西药类', isCategory: true },
  { id: 13, itemName: '17.西药费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 14, itemName: '（五）中药类', isCategory: true },
  { id: 15, itemName: '18.中成药费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 16, itemName: '19.中草药费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 17, itemName: '（六）耗材类', isCategory: true },
  { id: 18, itemName: '21.检查用一次性医用材料费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 19, itemName: '22.治疗用一次性医用材料费', amount: null, classA: null, classB: null, selfPay: null, other: null },
  { id: 20, itemName: '金额合计', amount: null, classA: null, classB: null, selfPay: null, other: null, isTotal: true }
])

// Fund Pay Items
const fundPayItems = ref([
  { name: '基本医疗保险统筹基金支付', amount: null },
  { name: '大病保险资金支付', amount: null },
  { name: '医疗救助资金支付', amount: null },
  { name: '其他支付', amount: null }
])

// QC Panel
const qcVisible = ref(false)
const qcReport = reactive<SettlementQCReport>({
  isValid: true,
  errorCount: 0,
  warningCount: 0,
  results: []
})

// Table columns
const outpatientColumns = [
  { title: '诊断名称', dataIndex: 'diagnosisName', width: '25%' },
  { title: '诊断代码', dataIndex: 'diagnosisCode', width: '25%' },
  { title: '手术及操作名称', dataIndex: 'procedureName', width: '25%' },
  { title: '手术及操作代码', dataIndex: 'procedureCode', width: '25%' }
]

const diagnosisColumns = [
  { title: '', dataIndex: 'rowLabel', width: 80 },
  { title: '西医诊断', dataIndex: 'westDiagnosis' },
  { title: '疾病代码', dataIndex: 'westCode', width: 100 },
  { title: '入院病情', dataIndex: 'admissionCondition', width: 80 },
  { title: '中医诊断', dataIndex: 'tcmDiagnosis' },
  { title: '中医代码', dataIndex: 'tcmCode', width: 100 }
]

const surgeryColumns = [
  { title: '', dataIndex: 'rowLabel', width: 80 },
  { title: '手术名称', dataIndex: 'name' },
  { title: '手术代码', dataIndex: 'code', width: 100 },
  { title: '手术日期', dataIndex: 'date', width: 100 },
  { title: '麻醉方式', dataIndex: 'anesthesia', width: 80 },
  { title: '术者姓名', dataIndex: 'surgeonName', width: 80 },
  { title: '术者代码', dataIndex: 'surgeonCode', width: 80 }
]

const feeColumns = [
  { title: '项目名称', dataIndex: 'itemName', width: 200 },
  { title: '金额', dataIndex: 'amount', width: 100 },
  { title: '甲类', dataIndex: 'classA', width: 100 },
  { title: '乙类', dataIndex: 'classB', width: 100 },
  { title: '自费', dataIndex: 'selfPay', width: 100 },
  { title: '其他', dataIndex: 'other', width: 100 }
]

// State
const saving = ref(false)

// Handlers
const handleSave = async () => {
  saving.value = true
  try {
    await new Promise(r => setTimeout(r, 1000))
    message.success('保存成功')
  } finally {
    saving.value = false
  }
}

const handlePrint = () => {
  window.print()
}

const handleValidate = () => {
  qcVisible.value = true
  // Mock validation
  qcReport.errorCount = 2
  qcReport.warningCount = 3
  qcReport.results = [
    { ruleId: 'QC001', field: '姓名', message: '姓名不能为空', severity: 'error', passed: false },
    { ruleId: 'QC003', field: '主诊断代码', message: '请填写主诊断代码', severity: 'error', passed: false },
    { ruleId: 'QC005', field: '住院天数', message: '住院天数与入出院日期不一致', severity: 'warning', passed: false }
  ]
  qcReport.isValid = qcReport.errorCount === 0
}
</script>

<style scoped lang="scss">
.settlement-form {
  min-height: 100vh;
  background: #f1f5f9;
}

.page-header {
  background: #fff;
  padding: 12px 24px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}

.content-wrapper {
  padding: 16px 24px;
}

.form-container {
  background: #fff;
  border: 2px solid #1e293b;
  padding: 24px;
  font-size: 13px;
}

.form-title {
  text-align: center;
  margin-bottom: 16px;
  font-size: 22px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  
  .region-input {
    width: 80px;
    text-align: center;
    border: none;
    border-bottom: 1px solid #000;
    font-size: 18px;
    font-weight: 700;
  }
}

.header-fields {
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
  
  .field-label {
    font-weight: 500;
    margin-right: 8px;
  }
  
  .inline-input {
    border: none;
    border-bottom: 1px solid #000;
    border-radius: 0;
    
    &:focus {
      box-shadow: none;
      border-bottom-color: #2563eb;
    }
  }
}

.form-section {
  border: 1px solid #1e293b;
  margin-bottom: -1px;
  
  .section-header {
    background: #dbeafe;
    padding: 6px 12px;
    font-weight: 600;
    text-align: center;
    border-bottom: 1px solid #1e293b;
  }
  
  .section-body {
    padding: 12px;
  }
}

.form-row {
  margin-bottom: 8px;
  
  .field-label {
    display: block;
    font-size: 12px;
    color: #64748b;
    margin-bottom: 2px;
  }
}

.text-right {
  text-align: right;
}

.w-full {
  width: 100%;
}

.w-40 {
  width: 160px;
}

.w-48 {
  width: 192px;
}

.w-24 {
  width: 96px;
}

.mt-2 {
  margin-top: 8px;
}

.qc-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  height: calc(100vh - 120px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  
  .qc-header {
    padding: 12px 16px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
  }
  
  .qc-summary {
    padding: 16px;
    display: flex;
    gap: 24px;
    border-bottom: 1px solid #e2e8f0;
  }
  
  .qc-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
  
  .qc-item {
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 12px;
    
    &.error {
      background: #fef2f2;
      border-left: 3px solid #ef4444;
    }
    
    &.warning {
      background: #fffbeb;
      border-left: 3px solid #f59e0b;
    }
    
    .qc-rule {
      font-weight: 600;
      margin-right: 8px;
      color: #334155;
    }
    
    .qc-field {
      color: #64748b;
      margin-right: 8px;
    }
    
    .qc-message {
      color: #1e293b;
    }
  }
}

@media print {
  .page-header, .qc-panel {
    display: none !important;
  }
  
  .content-wrapper {
    padding: 0;
  }
  
  .form-container {
    box-shadow: none;
  }
}

/* Additional styles for Section 3 & 4 */
.sub-section-title {
  font-weight: 600;
  font-size: 13px;
  color: #1e293b;
  margin-bottom: 8px;
  padding-left: 4px;
  border-left: 3px solid #6366f1;
}

.compact-table {
  :deep(.ant-table-thead > tr > th) {
    padding: 6px 8px;
    font-size: 12px;
    background: #f8fafc;
  }
  
  :deep(.ant-table-tbody > tr > td) {
    padding: 4px 6px;
  }
  
  :deep(.ant-input) {
    font-size: 12px;
  }
}

.row-label {
  font-size: 11px;
  color: #64748b;
  white-space: nowrap;
}

.payment-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px;
  
  .payment-title {
    font-weight: 600;
    font-size: 13px;
    color: #1e293b;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e2e8f0;
  }
  
  .payment-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    font-size: 12px;
    
    span {
      color: #475569;
    }
  }
}

.fee-table {
  :deep(.ant-table-tbody > tr > td:first-child) {
    text-align: left;
    padding-left: 8px;
  }
}

.font-bold {
  font-weight: 600;
}
</style>
