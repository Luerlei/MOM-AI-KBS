<template>
  <div class="trends-page">
    <!-- 顶部工具栏 -->
    <a-card size="small" style="margin-bottom: 16px">
      <a-space wrap align="center">
        <a-select
          v-model:value="selectedDatasetId"
          placeholder="选择数据集"
          style="width: 280px"
          show-search
          option-filter-prop="label"
          :options="datasetOptions"
          @change="onDatasetChange"
        />
        <a-select
          v-model:value="selectedModelId"
          placeholder="选择预测模型"
          style="width: 220px"
          :options="forecastModelOptions"
          @change="onModelChange"
        />
        <a-radio-group v-model:value="predictMode" button-style="solid">
          <a-radio-button value="future">预测未来</a-radio-button>
          <a-radio-button value="backtest">回测对照</a-radio-button>
        </a-radio-group>
        <template v-if="predictMode === 'backtest'">
          <span class="param-label">训练点数</span>
          <a-input-number
            v-model:value="startIndex"
            :min="3"
            :max="Math.max(3, currentPointCount - 1)"
            :precision="0"
            style="width: 110px"
          />
          <span class="param-hint">/ {{ currentPointCount }}（留 {{ backtestActualCount }} 点对照）</span>
        </template>
        <a-input-number
          v-model:value="horizon"
          :min="1"
          :max="24"
          :precision="0"
          addon-before="预测步数"
          style="width: 180px"
        />
        <a-checkbox v-model:checked="enableAnalysis">AI分析</a-checkbox>
        <a-button
          type="primary"
          :loading="predicting"
          :disabled="!selectedDatasetId || !selectedModelId"
          @click="onRunForecast"
        >
          <template #icon><ThunderboltOutlined /></template>
          开始预测
        </a-button>
        <a-divider type="vertical" />
        <a-select
          v-model:value="selectedStatModel"
          placeholder="统计模型"
          style="width: 120px"
          :options="statModelOptions"
        />
        <a-tooltip
          v-if="selectedStatModel === 'arima' || selectedStatModel === 'prophet'"
          title="启用后 ARIMA/Prophet 会使用数据集的协变量（exog）增强预测。请在数据集管理页配置协变量。"
        >
          <a-checkbox v-model:checked="useCovariates">使用协变量</a-checkbox>
        </a-tooltip>
        <a-button
          :loading="runningStatForecast"
          :disabled="!selectedDatasetId"
          @click="onRunStatForecast"
        >
          <template #icon><ThunderboltOutlined /></template>
          统计预测
        </a-button>
        <a-button
          :disabled="!analysisText && !predicting"
          :loading="predicting"
          @click="analysisDrawerVisible = true"
        >
          <template #icon><FileTextOutlined /></template>
          AI分析报告
        </a-button>
        <a-button
          :disabled="!selectedDatasetId"
          @click="cvDrawerVisible = true"
        >
          <template #icon><ExperimentOutlined /></template>
          交叉验证
        </a-button>
        <a-button
          :disabled="!selectedDatasetId"
          @click="compareDrawerVisible = true"
        >
          <template #icon><BarChartOutlined /></template>
          多模型对比
        </a-button>
        <a-divider type="vertical" />
        <a-button
          :loading="autoSelecting"
          :disabled="!selectedDatasetId"
          @click="onAutoSelect"
        >
          <template #icon><TrophyOutlined /></template>
          自动选模型
        </a-button>
        <a-button
          :loading="ensembling"
          :disabled="!selectedDatasetId"
          @click="onEnsembleForecast"
        >
          <template #icon><BlockOutlined /></template>
          集成预测
        </a-button>
        <a-button
          :disabled="!selectedDatasetId"
          @click="featuresDrawerVisible = true"
        >
          <template #icon><FunctionOutlined /></template>
          特征工程
        </a-button>
        <a-button
          :disabled="!selectedDatasetId"
          @click="anomalyDrawerVisible = true"
        >
          <template #icon><WarningOutlined /></template>
          异常检测
        </a-button>
        <a-button
          :loading="optimizing"
          :disabled="!selectedDatasetId"
          @click="onOptimizeParams"
        >
          <template #icon><TuningOutlined /></template>
          超参优化
        </a-button>
        <a-tag v-if="switchingModel" color="processing">切换中...</a-tag>
      </a-space>
    </a-card>

    <a-empty
      v-if="!selectedDatasetId"
      description="请先选择一个数据集"
      style="padding: 60px 0"
    />

    <template v-else>
      <!-- 关键指标小卡片 第1行 -->
      <a-row :gutter="[12, 12]" style="margin-bottom: 16px">
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-blue"><DatabaseOutlined /></div>
            <a-statistic title="数据点数" :value="stats?.count ?? 0" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-cyan"><CalculatorOutlined /></div>
            <a-statistic title="均值" :value="stats?.avg ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-green"><ArrowDownOutlined /></div>
            <a-statistic title="最小值" :value="stats?.min ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-red"><ArrowUpOutlined /></div>
            <a-statistic title="最大值" :value="stats?.max ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-purple"><VerticalAlignTopOutlined /></div>
            <a-statistic title="首值" :value="stats?.first ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-orange"><VerticalAlignBottomOutlined /></div>
            <a-statistic title="末值" :value="stats?.last ?? 0" :suffix="unitText" :precision="dataPrecision" />
          </a-card>
        </a-col>
      </a-row>

      <!-- 关键指标小卡片 第2行 -->
      <a-row :gutter="[12, 12]" style="margin-bottom: 16px">
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon" :class="trendDirColor === 'green' ? 'kpi-green' : trendDirColor === 'red' ? 'kpi-red' : 'kpi-gray'">
              <RiseOutlined v-if="trendDirColor === 'green'" />
              <FallOutlined v-else-if="trendDirColor === 'red'" />
              <MinusOutlined v-else />
            </div>
            <div class="mini-text">
              <div class="mini-label">趋势方向</div>
              <a-tag :color="trendDirColor" style="margin: 0">{{ trendDirText }}</a-tag>
            </div>
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-purple"><RocketOutlined /></div>
            <a-statistic title="趋势强度 R²" :value="stats?.trend_strength ?? 0" :precision="4" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon" :class="(stats?.growth_rate ?? 0) >= 0 ? 'kpi-green' : 'kpi-red'">
              <ArrowUpOutlined v-if="(stats?.growth_rate ?? 0) >= 0" />
              <ArrowDownOutlined v-else />
            </div>
            <a-statistic
              title="环比增长率"
              :value="stats?.growth_rate ?? 0"
              suffix="%"
              :precision="2"
              :value-style="{ color: (stats?.growth_rate ?? 0) >= 0 ? '#52c41a' : '#f5222d' }"
            />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-orange"><AlertOutlined /></div>
            <a-statistic title="波动性 CV" :value="stats?.volatility ?? 0" suffix="%" :precision="2" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-blue"><FieldTimeOutlined /></div>
            <a-statistic title="耗时" :value="forecastInfo?.duration_ms ?? 0" suffix="ms" />
          </a-card>
        </a-col>
        <a-col :xs="12" :sm="8" :md="6" :lg="4" :xl="4">
          <a-card size="small" :loading="loadingTrend" class="mini-card">
            <div class="mini-icon kpi-cyan"><AimOutlined /></div>
            <div class="mini-text">
              <div class="mini-label">预测范围</div>
              <div class="mini-value">{{ forecastRange }}</div>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 长文本摘要卡片（占满一行） -->
      <a-card size="small" style="margin-bottom: 16px" :loading="loadingTrend">
        <template #title>
          <span><FileTextOutlined /> 数据与预测摘要</span>
        </template>
        <div class="long-summary">
          <!-- 数据集元信息 -->
          <div class="long-summary-meta">
            <span class="meta-item"><b>数据频率：</b>{{ frequencyText }}</span>
            <span class="meta-item"><b>单位：</b>{{ unitText || '—' }}</span>
          </div>
          <!-- 预测元信息 -->
          <div v-if="forecastInfo" class="long-summary-meta" style="margin-top: 8px">
            <span class="meta-item"><b>预测模型：</b>{{ forecastInfo.model_name }}</span>
            <span v-if="isBacktest" class="meta-item"><b>训练点数：</b>{{ forecastInfo.start_index }}</span>
            <span v-if="isBacktest" class="meta-item"><b>对照点数：</b>{{ forecastInfo.actuals.length }}</span>
            <span v-else class="meta-item"><b>预测步数：</b>{{ forecastInfo.forecasts.length }}</span>
            <span v-if="!isBacktest" class="meta-item"><b>预测范围：</b>{{ forecastRange }}</span>
            <span class="meta-item"><b>耗时：</b>{{ forecastInfo.duration_ms }} ms</span>
            <span class="meta-item"><b>任务 ID：</b>#{{ forecastInfo.task_id }}</span>
          </div>
          <!-- 回测误差指标 -->
          <div v-if="isBacktest && hasActuals" class="long-summary-meta" style="margin-top: 8px">
            <span class="meta-item"><b>MAE：</b>{{ fmtVal(metricsData.mae) }}{{ unitText }}</span>
            <span class="meta-item"><b>MAPE：</b>{{ Number(metricsData.mape || 0).toFixed(2) }}%</span>
            <span class="meta-item"><b>RMSE：</b>{{ fmtVal(metricsData.rmse) }}{{ unitText }}</span>
            <span class="meta-item"><b>最大误差：</b>{{ fmtVal(metricsData.max_error) }}{{ unitText }}</span>
          </div>
          <!-- 回测扩展指标 -->
          <div v-if="isBacktest && hasActuals && hasExtendedMetrics" class="long-summary-meta" style="margin-top: 8px">
            <span class="meta-item"><b>MASE：</b>{{ metricVal(metricsData, 'mase').toFixed(4) }}</span>
            <span class="meta-item"><b>sMAPE：</b>{{ metricVal(metricsData, 'smape').toFixed(2) }}%</span>
            <span class="meta-item"><b>Pinball Loss：</b>{{ metricVal(metricsData, 'pinball_loss').toFixed(4) }}</span>
            <span class="meta-item"><b>Coverage：</b>{{ metricVal(metricsData, 'coverage').toFixed(2) }}%</span>
            <span class="meta-item">
              <b>rMAE：</b>
              <a-tag :color="metricVal(metricsData, 'rmae') < 1 ? 'green' : 'red'" style="margin: 0">
                {{ metricVal(metricsData, 'rmae').toFixed(4) }}
              </a-tag>
              <span class="param-hint">{{ metricVal(metricsData, 'rmae') < 1 ? '优于Naive' : '不如Naive' }}</span>
            </span>
            <span class="meta-item"><b>Naive基线MAE：</b>{{ fmtVal(baselineVal(metricsData, 'naive_mae')) }}{{ unitText }}</span>
            <span class="meta-item"><b>SeasonalNaive基线MAE：</b>{{ fmtVal(baselineVal(metricsData, 'seasonal_naive_mae')) }}{{ unitText }}</span>
          </div>
          <!-- 协变量信息 -->
          <div v-if="hasCovariatesInfo" class="long-summary-meta" style="margin-top: 8px">
            <span class="meta-item">
              <b>协变量：</b>
              <a-tag color="cyan" style="margin: 0">已启用 {{ covariateNames.length }} 个</a-tag>
            </span>
            <span class="meta-item"><b>协变量列表：</b>{{ covariateNames.join(', ') }}</span>
          </div>
          <a-divider v-if="summaryText" style="margin: 12px 0" />
          <div v-if="summaryText" class="long-summary-text">{{ summaryText }}</div>
          <a-empty v-else-if="!forecastInfo" description="尚未执行预测" :image="simpleImage" />
        </div>
      </a-card>

      <!-- 趋势预测图表 -->
      <a-card title="趋势预测图表" style="margin-bottom: 16px">
        <a-spin :spinning="loadingTrend">
          <div ref="chartRef" class="chart-container"></div>
          <a-empty
            v-if="!loadingTrend && !trendData"
            description="暂无数据"
          />
        </a-spin>
        <div v-if="trendData" class="chart-legend">
          <span class="legend-item"><i class="dot history"></i>历史数据</span>
          <span class="legend-item"><i class="dot forecast"></i>预测数据</span>
          <span v-if="hasActuals" class="legend-item"><i class="dot actual"></i>实际数据</span>
          <span class="legend-item"><i class="band"></i>0.1-0.9 置信区间</span>
          <span class="legend-item"><i class="dot label"></i>标注点</span>
        </div>
      </a-card>

      <!-- 季节性分解（STL） -->
      <a-card title="季节性分解（STL）" style="margin-bottom: 16px">
        <template #extra>
          <a-button
            type="primary"
            size="small"
            :loading="decompLoading"
            :disabled="!selectedDatasetId"
            @click="onGenerateDecomp"
          >生成分解</a-button>
        </template>
        <a-spin :spinning="decompLoading">
          <div v-if="decompData && decompData.success" class="decomp-info">
            <a-tag color="blue">季节性强度：{{ (decompData.seasonal_strength ?? 0).toFixed(4) }}</a-tag>
            <a-tag color="orange">季节振幅：{{ (decompData.seasonal_amplitude ?? 0).toFixed(4) }}</a-tag>
            <a-tag v-if="decompData.frequency" color="green">频率：{{ decompData.frequency }}</a-tag>
            <a-tag v-if="decompData.preprocess" color="default">
              预处理：填充 {{ decompData.preprocess.missing_filled }} 个缺失，修正 {{ decompData.preprocess.outliers_fixed }} 个异常
            </a-tag>
          </div>
          <div
            v-if="decompData && decompData.success"
            ref="decompChartRef"
            class="decomp-chart-container"
          ></div>
          <a-empty
            v-else-if="decompData && !decompData.success"
            :description="decompData.message || '数据量不足，无法进行季节性分解'"
            :image="simpleImage"
          />
          <a-empty
            v-else
            description="点击「生成分解」按钮查看 STL 季节性分解结果"
            :image="simpleImage"
          />
        </a-spin>
      </a-card>

      <!-- 历史评估记录（图表下方） -->
      <a-card title="历史评估记录" size="small">
        <a-table
          :columns="taskColumns"
          :data-source="taskList"
          :loading="loadingTasks"
          :pagination="taskPagination"
          row-key="id"
          size="small"
          :scroll="{ x: 900 }"
          @change="onTaskPageChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
            <template v-if="column.key === 'mode'">
              <a-tag :color="record.start_index != null ? 'purple' : 'blue'" size="small">
                {{ record.start_index != null ? '回测' : '预测' }}
              </a-tag>
            </template>
            <template v-if="column.key === 'status'">
              <a-tag :color="statusColor(record.status)">{{ statusText(record.status) }}</a-tag>
            </template>
            <template v-if="column.key === 'duration_ms'">
              {{ record.duration_ms }} ms
            </template>
            <template v-if="column.key === 'action'">
              <a-space size="small">
                <a-button
                  type="link"
                  size="small"
                  :disabled="record.status !== 'success'"
                  @click="onViewTask(record)"
                >查看</a-button>
                <a-dropdown>
                  <a-button type="link" size="small" :disabled="record.status !== 'success'">导出</a-button>
                  <template #overlay>
                    <a-menu @click="(e) => onExportTask(record, e.key)">
                      <a-menu-item key="excel">Excel</a-menu-item>
                      <a-menu-item key="csv">CSV</a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </template>

    <!-- AI 增强分析报告抽屉 -->
    <a-drawer
      v-model:open="analysisDrawerVisible"
      title="AI 增强分析报告"
      placement="right"
      width="560"
    >
      <a-spin :spinning="predicting">
        <div v-if="analysisText" class="analysis-report">
          <pre>{{ analysisText }}</pre>
        </div>
        <a-empty v-else description="执行预测后将生成 AI 分析报告" :image="simpleImage" />
      </a-spin>
    </a-drawer>

    <!-- 交叉验证抽屉 -->
    <a-drawer
      v-model:open="cvDrawerVisible"
      title="交叉验证"
      placement="right"
      width="640"
    >
      <!-- 配置区 -->
      <div class="cv-config">
        <a-space wrap align="center">
          <span class="param-label">切分次数 n_splits</span>
          <a-input-number v-model:value="cvConfig.n_splits" :min="2" :max="10" :precision="0" style="width: 100px" />
          <span class="param-label">预测步数 horizon</span>
          <a-input-number v-model:value="cvConfig.horizon" :min="1" :max="12" :precision="0" style="width: 100px" />
        </a-space>
        <div style="margin-top: 8px">
          <span class="param-label" style="margin-right: 8px">切分策略</span>
          <a-radio-group v-model:value="cvConfig.strategy" button-style="solid">
            <a-radio-button value="expanding">expanding（扩展窗口）</a-radio-button>
            <a-radio-button value="sliding">sliding（滑动窗口）</a-radio-button>
          </a-radio-group>
        </div>
        <a-button
          type="primary"
          :loading="runningCV"
          :disabled="!selectedDatasetId"
          style="margin-top: 12px"
          @click="onRunCV"
        >
          <template #icon><ExperimentOutlined /></template>
          执行交叉验证
        </a-button>
      </div>

      <a-divider style="margin: 16px 0" />

      <!-- 结果展示 -->
      <a-spin :spinning="runningCV">
        <div v-if="cvResult">
          <div class="cv-summary">
            <span class="meta-item"><b>模型：</b>{{ cvResult.model_name }}</span>
            <span class="meta-item"><b>策略：</b>{{ cvResult.strategy }}</span>
            <span class="meta-item"><b>切分次数：</b>{{ cvResult.n_splits }}</span>
            <span class="meta-item"><b>预测步数：</b>{{ cvResult.horizon }}</span>
          </div>

          <!-- 各切分 MAE 趋势图 -->
          <div class="cv-section-title">各切分点 MAE 趋势</div>
          <div ref="cvChartRef" class="cv-chart-container"></div>

          <!-- 平均指标表格 -->
          <div class="cv-section-title">平均指标</div>
          <a-table
            :columns="cvAvgColumns"
            :data-source="cvAvgRows"
            :pagination="false"
            row-key="name"
            size="small"
            class="cv-metrics-table"
          />

          <!-- 每次切分明细表格 -->
          <div class="cv-section-title" style="margin-top: 16px">每次切分明细</div>
          <a-table
            :columns="cvSplitColumns"
            :data-source="cvResult.splits"
            :pagination="false"
            row-key="split_idx"
            size="small"
            class="cv-split-table"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'status'">
                <a-tag :color="record.status === 'success' ? 'green' : 'red'">
                  {{ record.status === 'success' ? '成功' : '失败' }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </div>
        <a-empty v-else description="配置参数后点击执行按钮" :image="simpleImage" />
      </a-spin>
    </a-drawer>

    <!-- 多模型对比抽屉 -->
    <a-drawer
      v-model:open="compareDrawerVisible"
      title="多模型对比"
      placement="right"
      width="720"
    >
      <a-space wrap align="center" style="margin-bottom: 12px">
        <a-button
          type="primary"
          :loading="runningCompare"
          :disabled="!selectedDatasetId"
          @click="onRunCompare"
        >
          <template #icon><BarChartOutlined /></template>
          执行多模型对比
        </a-button>
      </a-space>

      <a-spin :spinning="runningCompare">
        <div v-if="compareResult">
          <!-- 自动回测起点提示 -->
          <a-alert
            v-if="compareResult.start_index != null"
            type="info"
            show-icon
            style="margin-bottom: 12px"
            :message="`自动回测起点：${compareResult.start_index}，对照点数：${compareResult.actual_count}`"
          />

          <!-- 基线参考信息 -->
          <div class="compare-baselines">
            <span class="meta-item"><b>Naive MAE：</b>{{ fmtVal(compareResult.baselines?.naive_mae) }}{{ unitText }}</span>
            <span class="meta-item"><b>SeasonalNaive MAE：</b>{{ fmtVal(compareResult.baselines?.seasonal_naive_mae) }}{{ unitText }}</span>
          </div>

          <!-- 最优模型提示 -->
          <a-alert
            v-if="compareResult.best_model"
            type="success"
            show-icon
            class="best-model-alert"
            :message="`最优模型：${compareResult.best_model.model_name}（${compareResult.best_model.metric_name}=${compareResult.best_model.metric_value.toFixed(4)}, rMAE=${compareResult.best_model.rmae.toFixed(4)}）`"
          />

          <!-- 模型对比表格 -->
          <a-table
            :columns="compareColumns"
            :data-source="compareResult.models"
            :pagination="false"
            row-key="model_config_id"
            size="small"
            class="compare-table"
            :row-class-name="compareRowClass"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'rmae'">
                <span :style="{ color: metricVal(record.metrics, 'rmae') < 1 ? '#52c41a' : metricVal(record.metrics, 'rmae') > 1 ? '#f5222d' : 'inherit' }">
                  {{ metricVal(record.metrics, 'rmae').toFixed(4) }}
                </span>
              </template>
              <template v-if="column.key === 'status'">
                <a-tag :color="record.status === 'success' ? 'green' : 'red'">
                  {{ record.status === 'success' ? '成功' : '失败' }}
                </a-tag>
              </template>
            </template>
          </a-table>
        </div>
        <a-empty v-else description="点击执行按钮开始多模型对比" :image="simpleImage" />
      </a-spin>
    </a-drawer>

    <!-- B1: 自动模型选择抽屉 -->
    <a-drawer
      v-model:open="autoSelectDrawerVisible"
      title="自动模型选择结果"
      placement="right"
      width="600"
    >
      <a-spin :spinning="autoSelecting">
        <div v-if="autoSelectResult">
          <a-alert
            v-if="autoSelectResult.best_model?.recommendation"
            :message="autoSelectResult.best_model.recommendation"
            type="success"
            show-icon
            style="margin-bottom: 16px"
          />
          <a-descriptions :column="2" size="small" bordered style="margin-bottom: 16px">
            <a-descriptions-item label="CV折数">{{ autoSelectResult.n_splits }}</a-descriptions-item>
            <a-descriptions-item label="预测步长">{{ autoSelectResult.horizon }}</a-descriptions-item>
          </a-descriptions>
          <h4>模型排行榜</h4>
          <a-table
            :columns="[
              { title: '排名', key: 'rank', width: 60 },
              { title: '模型', dataIndex: 'model', key: 'model' },
              { title: 'MAE', dataIndex: 'avg_mae', key: 'mae' },
              { title: 'RMSE', dataIndex: 'avg_rmse', key: 'rmse' },
              { title: 'MAPE', dataIndex: 'avg_mape', key: 'mape' },
              { title: '成功率', dataIndex: 'success_rate', key: 'success_rate' },
            ]"
            :data-source="(autoSelectResult.ranking || []).map((r: any, i: number) => ({ ...r, rank: i + 1, key: i }))"
            size="small"
            :pagination="false"
            style="margin-bottom: 16px"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'mae'">
                <a-tag :color="record.rank === 1 ? 'green' : 'default'">{{ record.avg_mae ?? '-' }}</a-tag>
              </template>
            </template>
          </a-table>
        </div>
        <a-empty v-else description="点击「自动选模型」按钮开始评估" :image="simpleImage" />
      </a-spin>
    </a-drawer>

    <!-- B3: 特征工程抽屉 -->
    <a-drawer
      v-model:open="featuresDrawerVisible"
      title="高级特征工程"
      placement="right"
      width="700"
      @after-open="onFeaturesDrawerOpen"
    >
      <a-spin :spinning="featuresLoading">
        <div v-if="featuresResult">
          <a-alert :message="featuresResult.description" type="info" show-icon style="margin-bottom: 16px" />
          <a-descriptions :column="2" size="small" bordered style="margin-bottom: 16px">
            <a-descriptions-item label="特征数">{{ featuresResult.n_features }}</a-descriptions-item>
            <a-descriptions-item label="特征列表">{{ featuresResult.feature_names?.join(', ') }}</a-descriptions-item>
          </a-descriptions>
          <h4>特征值预览（前10行）</h4>
          <a-table
            :columns="featuresPreviewColumns"
            :data-source="featuresPreviewData"
            size="small"
            :pagination="false"
            :scroll="{ x: 800 }"
          />
        </div>
        <a-empty v-else description="加载数据中..." :image="simpleImage" />
      </a-spin>
    </a-drawer>

    <!-- B4: 异常检测抽屉 -->
    <a-drawer
      v-model:open="anomalyDrawerVisible"
      title="统计异常检测"
      placement="right"
      width="650"
    >
      <a-space direction="vertical" style="width: 100%; margin-bottom: 16px">
        <a-radio-group v-model:value="anomalyMethod" button-style="solid">
          <a-radio-button value="stl_residual">STL残差</a-radio-button>
          <a-radio-button value="isolation_forest">孤立森林</a-radio-button>
          <a-radio-button value="change_point">变点检测</a-radio-button>
        </a-radio-group>
        <a-button type="primary" :loading="anomalyLoading" @click="onDetectAnomalies">
          执行检测
        </a-button>
      </a-space>
      <a-spin :spinning="anomalyLoading">
        <div v-if="anomalyResult">
          <a-alert :message="anomalyResult.summary" type="warning" show-icon style="margin-bottom: 16px" />
          <div v-if="anomalyResult.change_points?.length" style="margin-bottom: 12px">
            <h4>变点位置</h4>
            <a-tag v-for="cp in anomalyResult.change_points" :key="cp" color="orange">索引 {{ cp }}</a-tag>
          </div>
          <h4>异常点列表</h4>
          <a-table
            v-if="anomalyResult.anomaly_scores?.length"
            :columns="[
              { title: '索引', dataIndex: 'index', key: 'index', width: 80 },
              { title: '异常得分', dataIndex: 'score', key: 'score' },
              { title: '原始值', dataIndex: 'value', key: 'value' },
            ]"
            :data-source="anomalyResult.anomaly_scores.map((s: any, i: number) => ({ ...s, key: i }))"
            size="small"
            :pagination="{ pageSize: 10 }"
          />
          <a-empty v-else description="未检测到异常点" :image="simpleImage" />
        </div>
        <a-empty v-else description="选择检测方法后点击执行" :image="simpleImage" />
      </a-spin>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import { Empty, message } from 'ant-design-vue'
import { ThunderboltOutlined } from '@ant-design/icons-vue'
import {
  DatabaseOutlined, CalculatorOutlined, RiseOutlined, FallOutlined, MinusOutlined,
  RocketOutlined, ArrowUpOutlined, ArrowDownOutlined, AlertOutlined,
  FileTextOutlined, FieldTimeOutlined,
  VerticalAlignTopOutlined, VerticalAlignBottomOutlined, AimOutlined,
  ExperimentOutlined, BarChartOutlined,
  TrophyOutlined, BlockOutlined, FunctionOutlined, WarningOutlined, TuningOutlined,
} from '@ant-design/icons-vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'
import {
  getDatasetList,
} from '@/api/dataset'
import {
  runForecast,
  getTrendAnalysis,
  getForecastTasks,
  getForecastResultByTask,
  exportForecastResultUrl,
  runCrossValidation,
  compareModels,
  getDecomposition,
  runStatisticalForecast,
  autoSelectModel,
  ensembleForecast,
  getAdvancedFeatures,
  detectAnomalies,
  optimizeParams,
} from '@/api/forecast'
import { getModelList, activateModel } from '@/api/model'
import type {
  Dataset,
  TrendAnalysis,
  ForecastTask,
  PaginatedData,
  ModelConfig,
  CrossValidationResponse,
  ModelCompareResponse,
  DecompositionResponse,
} from '@/types'

const route = useRoute()
const appStore = useAppStore()
const { modelStatus } = storeToRefs(appStore)

const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE

// 数据集列表
const datasets = ref<Dataset[]>([])
const selectedDatasetId = ref<number | undefined>(undefined)
const datasetOptions = computed(() =>
  datasets.value.map((d) => ({ label: `${d.name}（${d.point_count} 点）`, value: d.id }))
)

// 预测模型列表
const forecastModels = ref<ModelConfig[]>([])
const selectedModelId = ref<number | undefined>(undefined)
const switchingModel = ref(false)
const forecastModelOptions = computed(() =>
  forecastModels.value.map((m) => ({
    label: `${m.name}${m.is_active ? ' ✓' : ''}`,
    value: m.id,
  }))
)

// 预测参数
const horizon = ref(6)
const predicting = ref(false)
const predictMode = ref<'future' | 'backtest'>('future')
const startIndex = ref(12)
const enableAnalysis = ref(true)

// 统计模型预测
const statModelOptions = [
  { label: 'ARIMA', value: 'arima' },
  { label: 'ETS', value: 'ets' },
  { label: 'Theta', value: 'theta' },
  { label: 'Prophet', value: 'prophet' },
]
const selectedStatModel = ref<'arima' | 'ets' | 'theta' | 'prophet'>('arima')
const runningStatForecast = ref(false)
const useCovariates = ref(false)

// 趋势数据
const loadingTrend = ref(false)
const trendData = ref<TrendAnalysis | null>(null)
const analysisText = ref('')
const analysisDrawerVisible = ref(false)

// 历史任务
const loadingTasks = ref(false)
const taskList = ref<ForecastTask[]>([])
const taskTotal = ref(0)
const taskPage = ref(1)
const taskPageSize = ref(10)
const taskPagination = computed(() => ({
  current: taskPage.value,
  pageSize: taskPageSize.value,
  total: taskTotal.value,
  showSizeChanger: false,
  showTotal: (t: number) => `共 ${t} 条`,
}))

// 图表
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

// STL 季节性分解图表
const decompLoading = ref(false)
const decompData = ref<DecompositionResponse | null>(null)
const decompChartRef = ref<HTMLElement | null>(null)
let decompChart: echarts.ECharts | null = null

// 交叉验证 MAE 图表
const cvChartRef = ref<HTMLElement | null>(null)
let cvChart: echarts.ECharts | null = null

// ===== 计算属性 =====
const hasForecastModel = computed(() => !!selectedModelId.value)
const forecastModelName = computed(() => {
  const m = forecastModels.value.find((m) => m.id === selectedModelId.value)
  return m?.model_name || ''
})

const stats = computed(() => trendData.value?.analysis.stats || null)
const forecastInfo = computed(() => trendData.value?.forecast || null)
const summaryText = computed(() => trendData.value?.analysis.summary || '')
const unitText = computed(() => trendData.value?.dataset.unit || '')
const frequencyText = computed(() => {
  const map: Record<string, string> = {
    daily: '每日', weekly: '每周', monthly: '每月',
    quarterly: '每季度', yearly: '每年', hourly: '每小时', other: '其他',
  }
  return map[trendData.value?.dataset.frequency || 'other'] || '其他'
})

const trendDirText = computed(() => {
  const map: Record<string, string> = { up: '上升', down: '下降', flat: '平稳' }
  return map[stats.value?.trend_direction || 'flat'] || '平稳'
})
const trendDirColor = computed(() => {
  const map: Record<string, string> = { up: 'green', down: 'red', flat: 'default' }
  return map[stats.value?.trend_direction || 'flat'] || 'default'
})

// 根据原始数据推断小数精度
const dataPrecision = computed(() => {
  const values = trendData.value?.history?.map((p) => p.value) || []
  if (values.length === 0) return 2
  let maxDecimals = 0
  for (const v of values) {
    const s = String(v)
    const dot = s.indexOf('.')
    if (dot >= 0) maxDecimals = Math.max(maxDecimals, s.length - dot - 1)
  }
  return Math.min(maxDecimals, 6)
})

const forecastRange = computed(() => {
  if (!forecastInfo.value || forecastInfo.value.forecasts.length === 0) return '—'
  const fs = forecastInfo.value.forecasts
  const p = dataPrecision.value
  return `${Math.min(...fs).toFixed(p)} ~ ${Math.max(...fs).toFixed(p)}${unitText.value}`
})

// 历史值带精度的格式化
function fmtVal(v: number | undefined | null): string {
  if (v == null) return '—'
  return Number(v).toFixed(dataPrecision.value)
}

const currentPointCount = computed(() => trendData.value?.dataset.point_count ?? 0)
const backtestActualCount = computed(() => Math.max(0, currentPointCount.value - startIndex.value))
const isBacktest = computed(() => forecastInfo.value?.is_backtest ?? false)
const hasActuals = computed(() => (forecastInfo.value?.actuals?.length ?? 0) > 0)
const metricsData = computed(() => forecastInfo.value?.metrics ?? { mae: 0, mape: 0, rmse: 0, max_error: 0 })

// 是否存在扩展指标（MASE / sMAPE / rMAE / baselines 等）
const hasExtendedMetrics = computed(() => {
  const m = metricsData.value as any
  if (!m || typeof m !== 'object') return false
  return (
    typeof m.mase === 'number' ||
    typeof m.smape === 'number' ||
    typeof m.pinball_loss === 'number' ||
    typeof m.coverage === 'number' ||
    typeof m.rmae === 'number' ||
    (m.baselines && typeof m.baselines === 'object')
  )
})

// 协变量信息（统计模型 ARIMAX 时存在）
const covariateNames = computed<string[]>(() => {
  const m = metricsData.value as any
  if (!m || typeof m !== 'object') return []
  if (m.used_covariates && Array.isArray(m.covariate_names)) {
    return m.covariate_names
  }
  return []
})
const hasCovariatesInfo = computed(() => covariateNames.value.length > 0)

// ===== 交叉验证 =====
const cvDrawerVisible = ref(false)
const runningCV = ref(false)
const cvResult = ref<CrossValidationResponse | null>(null)
const cvConfig = reactive({
  n_splits: 5,
  horizon: 6,
  strategy: 'expanding' as 'expanding' | 'sliding',
})

// 交叉验证平均指标表格列
const cvAvgColumns = [
  { title: '指标名', dataIndex: 'name', key: 'name' },
  { title: '平均值', dataIndex: 'avg', key: 'avg', align: 'right' as const },
  { title: '标准差', dataIndex: 'std', key: 'std', align: 'right' as const },
]

// 交叉验证平均指标行数据（展平 baselines 等嵌套对象）
const cvAvgRows = computed(() => {
  if (!cvResult.value) return []
  const rows: { name: string; avg: string; std: string }[] = []
  const avg = cvResult.value.avg_metrics as any
  const std = cvResult.value.std_metrics as any
  if (!avg || typeof avg !== 'object') return rows
  for (const key of Object.keys(avg)) {
    const v = avg[key]
    if (typeof v === 'number') {
      rows.push({
        name: key,
        avg: v.toFixed(4),
        std: typeof std[key] === 'number' ? (std[key] as number).toFixed(4) : '—',
      })
    } else if (v && typeof v === 'object') {
      // 嵌套对象（如 baselines）
      for (const subKey of Object.keys(v)) {
        const sv = v[subKey]
        if (typeof sv === 'number') {
          rows.push({
            name: `${key}.${subKey}`,
            avg: sv.toFixed(4),
            std: '—',
          })
        }
      }
    }
  }
  return rows
})

// 交叉验证每次切分明细表格列
const cvSplitColumns = [
  { title: '切分序号', dataIndex: 'split_idx', key: 'split_idx', width: 90, align: 'center' as const },
  { title: '起点', dataIndex: 'start_index', key: 'start_index', width: 80, align: 'right' as const },
  { title: 'MAE', key: 'mae', width: 90, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'mae').toFixed(4) },
  { title: 'MAPE', key: 'mape', width: 90, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'mape').toFixed(2) + '%' },
  { title: 'RMSE', key: 'rmse', width: 90, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'rmse').toFixed(4) },
  { title: '状态', key: 'status', width: 80, align: 'center' as const },
  { title: '耗时(ms)', dataIndex: 'duration_ms', key: 'duration_ms', width: 100, align: 'right' as const },
]

async function onRunCV(): Promise<void> {
  if (!selectedDatasetId.value) return
  runningCV.value = true
  cvResult.value = null
  try {
    const res = await runCrossValidation({
      dataset_id: selectedDatasetId.value,
      n_splits: cvConfig.n_splits,
      horizon: cvConfig.horizon,
      strategy: cvConfig.strategy,
      skip_analysis: true,
    })
    cvResult.value = res
    await nextTick()
    renderCVChart()
  } catch (e: any) {
    message.error(e.message || '交叉验证失败')
  } finally {
    runningCV.value = false
  }
}

// ===== 多模型对比 =====
const compareDrawerVisible = ref(false)
const runningCompare = ref(false)
const compareResult = ref<ModelCompareResponse | null>(null)

// 多模型对比表格列
const compareColumns = [
  { title: '模型名称', dataIndex: 'model_name', key: 'model_name', width: 140, ellipsis: true },
  { title: '标识', dataIndex: 'model_identifier', key: 'model_identifier', width: 120, ellipsis: true },
  { title: 'MAE', key: 'mae', width: 80, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'mae').toFixed(4) },
  { title: 'MAPE', key: 'mape', width: 80, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'mape').toFixed(2) + '%' },
  { title: 'RMSE', key: 'rmse', width: 80, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'rmse').toFixed(4) },
  { title: 'MASE', key: 'mase', width: 80, align: 'right' as const, customRender: ({ record }: any) => metricVal(record.metrics, 'mase').toFixed(4) },
  { title: 'rMAE', key: 'rmae', width: 80, align: 'right' as const },
  { title: '耗时(ms)', dataIndex: 'duration_ms', key: 'duration_ms', width: 90, align: 'right' as const },
  { title: '状态', key: 'status', width: 70, align: 'center' as const },
]

function compareRowClass(record: any): string {
  if (!compareResult.value?.best_model) return ''
  return record.model_name === compareResult.value.best_model.model_name ? 'best-model-row' : ''
}

async function onRunCompare(): Promise<void> {
  if (!selectedDatasetId.value) return
  runningCompare.value = true
  compareResult.value = null
  try {
    const res = await compareModels({
      dataset_id: selectedDatasetId.value,
      horizon: horizon.value,
    })
    compareResult.value = res
  } catch (e: any) {
    message.error(e.message || '多模型对比失败')
  } finally {
    runningCompare.value = false
  }
}

// ===== 辅助：获取指标值（metrics 可能是 number 或 object） =====
function metricVal(m: any, key: string): number {
  if (!m || typeof m !== 'object') return 0
  const v = m[key]
  return typeof v === 'number' ? v : 0
}
function baselineVal(m: any, key: string): number {
  if (!m || typeof m !== 'object') return 0
  const bl = m.baselines
  if (!bl || typeof bl !== 'object') return 0
  const v = bl[key]
  return typeof v === 'number' ? v : 0
}

// ===== 任务列表列 =====
const taskColumns = [
  { title: '任务ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '模型', dataIndex: 'model_name', key: 'model_name', width: 180, ellipsis: true },
  { title: '模式', key: 'mode', width: 80, align: 'center' as const },
  { title: '步数', dataIndex: 'horizon', key: 'horizon', width: 70, align: 'right' as const },
  { title: '状态', dataIndex: 'status', key: 'status', width: 90, align: 'center' as const },
  { title: '耗时', dataIndex: 'duration_ms', key: 'duration_ms', width: 100, align: 'right' as const },
  { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160 },
  { title: '操作', key: 'action', width: 140, align: 'center' as const, fixed: 'right' as const },
]

// ===== 方法 =====
async function fetchDatasets(): Promise<void> {
  try {
    const res = await getDatasetList({ page: 1, page_size: 100 })
    datasets.value = res.items || []
    // 若 URL 带 dataset_id 参数则自动选中
    const qid = route.query.dataset_id
    if (qid && !selectedDatasetId.value) {
      const id = Number(qid)
      if (datasets.value.some((d) => d.id === id)) {
        selectedDatasetId.value = id
        await onDatasetChange(id)
        return
      }
    }
    // 默认选第一个
    if (!selectedDatasetId.value && datasets.value.length > 0) {
      selectedDatasetId.value = datasets.value[0].id
      await onDatasetChange(datasets.value[0].id)
    }
  } catch {
    datasets.value = []
  }
}

async function fetchForecastModels(): Promise<void> {
  try {
    const all = await getModelList()
    forecastModels.value = all.filter((m) => m.type === 'Forecast')
    // 默认选中当前启用的模型
    const active = forecastModels.value.find((m) => m.is_active)
    if (active) {
      selectedModelId.value = active.id
    } else if (forecastModels.value.length > 0 && !selectedModelId.value) {
      selectedModelId.value = forecastModels.value[0].id
    }
  } catch {
    forecastModels.value = []
  }
}

async function onModelChange(modelId: number): Promise<void> {
  // 选择哪个模型就自动启用哪个
  const target = forecastModels.value.find((m) => m.id === modelId)
  if (!target) return
  if (target.is_active) return  // 已启用无需切换

  switchingModel.value = true
  try {
    await activateModel(modelId)
    // 更新本地状态
    forecastModels.value.forEach((m) => (m.is_active = m.id === modelId))
    await appStore.loadModelStatus()
    message.success(`已切换到模型：${target.name}`)
  } catch (e: any) {
    message.error(e?.message || '模型切换失败')
  } finally {
    switchingModel.value = false
  }
}

async function onDatasetChange(id: number): Promise<void> {
  await Promise.all([fetchTrend(id), fetchTasks(id)])
}

async function fetchTrend(datasetId: number): Promise<void> {
  loadingTrend.value = true
  try {
    const data = await getTrendAnalysis(datasetId)
    trendData.value = data
    analysisText.value = data.forecast?.analysis || ''
    await nextTick()
    renderChart()
  } catch (e: any) {
    trendData.value = null
    analysisText.value = ''
  } finally {
    loadingTrend.value = false
  }
}

async function fetchTasks(datasetId: number): Promise<void> {
  loadingTasks.value = true
  try {
    const res: PaginatedData<ForecastTask> = await getForecastTasks(datasetId, taskPage.value, taskPageSize.value)
    taskList.value = res.items || []
    taskTotal.value = res.total || 0
  } catch {
    taskList.value = []
    taskTotal.value = 0
  } finally {
    loadingTasks.value = false
  }
}

function onTaskPageChange(pag: any): void {
  taskPage.value = pag.current
  if (selectedDatasetId.value) fetchTasks(selectedDatasetId.value)
}

async function onRunForecast(): Promise<void> {
  if (!selectedDatasetId.value) return
  predicting.value = true
  try {
    const payload: any = {
      dataset_id: selectedDatasetId.value,
      horizon: horizon.value,
      skip_analysis: !enableAnalysis.value,
    }
    if (predictMode.value === 'backtest') {
      payload.start_index = startIndex.value
    }
    const res = await runForecast(payload)
    const modeLabel = predictMode.value === 'backtest' ? '回测' : '预测'
    message.success(`${modeLabel}完成，耗时 ${res.task.duration_ms} ms`)
    // 刷新趋势与任务列表
    await Promise.all([
      fetchTrend(selectedDatasetId.value),
      fetchTasks(selectedDatasetId.value),
    ])
  } catch (e: any) {
    message.error(e?.message || '预测失败')
  } finally {
    predicting.value = false
  }
}

async function onViewTask(record: ForecastTask): Promise<void> {
  // 按 task_id 加载特定历史任务的预测结果，更新图表展示
  try {
    message.loading({ content: `正在加载任务 #${record.id} 的结果...`, key: 'viewTask', duration: 0 })
    const res = await getForecastResultByTask(record.id)
    if (trendData.value && res.result) {
      const t = res.task
      const r = res.result
      trendData.value.forecast = {
        forecasts: r.forecasts,
        quantiles: r.quantiles,
        future_times: r.future_times,
        actuals: r.actuals || [],
        metrics: r.metrics || {},
        model_name: r.model_name,
        duration_ms: t.duration_ms,
        analysis: r.analysis,
        task_id: t.id,
        start_index: t.start_index,
        horizon: t.horizon,
        is_backtest: t.start_index != null,
      }
      await nextTick()
      renderChart()
      message.success({ content: `已展示任务 #${record.id} 的预测结果`, key: 'viewTask' })
    }
  } catch (e: any) {
    message.error({ content: e?.message || '加载历史任务失败', key: 'viewTask' })
  }
}

function onExportTask(record: ForecastTask, format: 'excel' | 'csv'): void {
  const url = exportForecastResultUrl(record.id, format)
  window.open(url, '_blank')
}

// ===== 图表渲染 =====
function renderChart(): void {
  if (!chartRef.value || !trendData.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const data = trendData.value
  const history = data.history
  const fc = data.forecast
  const backtestMode = fc?.is_backtest && (fc.actuals?.length ?? 0) > 0

  const historyTimes = history.map((p) => p.time)
  const historyValues = history.map((p) => p.value)
  const forecastValues = fc ? fc.forecasts : []
  const futureTimes = fc ? fc.future_times : []

  let allTimes: string[]
  let historySeries: (number | null)[]
  let forecastSeries: (number | null)[]
  let actualSeries: (number | null)[]
  let lowerSeries: (number | null)[]
  let bandSeries: (number | null)[]
  let forecastStartIdx: number  // forecast 起点在 allTimes 中的索引

  if (backtestMode) {
    // 回测模式：future_times 是 historyTimes 的子集
    // allTimes = historyTimes（不追加 future_times，避免重复）
    allTimes = [...historyTimes]
    forecastStartIdx = fc!.start_index ?? 0
    const trainEnd = forecastStartIdx  // 训练数据最后一个点的索引

    // 历史系列：训练区间[0, trainEnd) 显示，对照区间[trainEnd, N) 设为 null（用 actual 线展示）
    historySeries = historyValues.map((v, i) => i < trainEnd ? v : null)
    // 训练段末尾连接预测段
    if (trainEnd > 0) {
      historySeries[trainEnd - 1] = historyValues[trainEnd - 1]
    }

    // 预测系列：训练区间 null，连接点 + 预测值
    forecastSeries = historyTimes.map(() => null)
    if (trainEnd > 0) {
      forecastSeries[trainEnd - 1] = historyValues[trainEnd - 1]
    }
    forecastValues.forEach((v, i) => {
      if (trainEnd + i < forecastSeries.length) {
        forecastSeries[trainEnd + i] = v
      }
    })

    // 实际值系列：从训练末点连接，显示对照区间全部真实值（不截断于预测步数）
    actualSeries = historyTimes.map(() => null)
    if (trainEnd > 0) {
      actualSeries[trainEnd - 1] = historyValues[trainEnd - 1]
    }
    for (let i = trainEnd; i < historyValues.length; i++) {
      actualSeries[i] = historyValues[i]
    }

    // 置信区间（基于预测段位置）
    lowerSeries = historyTimes.map(() => null)
    bandSeries = historyTimes.map(() => null)
  } else {
    // 未来预测模式：future_times 是新时间标签
    allTimes = [...historyTimes, ...futureTimes]
    forecastStartIdx = historyValues.length

    historySeries = [...historyValues, ...futureTimes.map(() => null)]
    forecastSeries = historyTimes.map(() => null)
    if (forecastValues.length > 0 && historyValues.length > 0) {
      forecastSeries[historyValues.length - 1] = historyValues[historyValues.length - 1]
    }
    forecastValues.forEach((v, i) => {
      forecastSeries[historyValues.length + i] = v
    })

    actualSeries = []
    lowerSeries = [...historyTimes.map(() => null), ...futureTimes.map(() => null)]
    bandSeries = [...historyTimes.map(() => null), ...futureTimes.map(() => null)]
  }

  // 置信区间带（0.1 - 0.9）
  const quantiles = fc?.quantiles || {}
  const p10: number[] = quantiles['0.1'] || []
  const p90: number[] = quantiles['0.9'] || []
  const hasBand = p10.length > 0 && p90.length > 0

  if (hasBand) {
    p10.forEach((v, i) => {
      lowerSeries[forecastStartIdx + i] = v
    })
    p90.forEach((v, i) => {
      const lo = p10[i] ?? v
      bandSeries[forecastStartIdx + i] = v - lo
    })
  }

  // 标注点（label 非空的历史点）
  const markPoints: any[] = []
  history.forEach((p, i) => {
    if (p.label && p.label.trim()) {
      markPoints.push({
        name: p.label,
        coord: [p.time, p.value],
        value: p.label,
        symbolSize: 28,
        itemStyle: { color: '#faad14' },
        label: { show: true, formatter: p.label, fontSize: 10, color: '#fff' },
      })
    }
  })

  // 预测起点虚线
  const markLines: any[] = []
  if (fc && allTimes.length > 0 && forecastStartIdx < allTimes.length) {
    markLines.push({
      xAxis: allTimes[forecastStartIdx],
      lineStyle: { type: 'dashed', color: '#fa8c16', width: 1.5 },
      label: { formatter: backtestMode ? '回测起点' : '预测起点', position: 'insideEndTop', fontSize: 10 },
    })
  }

  const series: any[] = [
    {
      name: '历史数据',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 5,
      data: historySeries,
      itemStyle: { color: '#1677ff' },
      lineStyle: { color: '#1677ff', width: 2 },
      markPoint: markPoints.length > 0 ? { data: markPoints } : undefined,
      markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines } : undefined,
      z: 3,
    },
  ]

  if (fc) {
    series.push({
      name: '预测数据',
      type: 'line',
      smooth: true,
      symbol: 'diamond',
      symbolSize: 7,
      data: forecastSeries,
      itemStyle: { color: '#fa8c16' },
      lineStyle: { color: '#fa8c16', width: 2, type: 'dashed' },
      z: 3,
    })
  }

  if (backtestMode) {
    series.push({
      name: '实际数据',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: actualSeries,
      itemStyle: { color: '#52c41a' },
      lineStyle: { color: '#52c41a', width: 2 },
      z: 3,
    })
  }

  if (hasBand) {
    series.push({
      name: '置信下界',
      type: 'line',
      symbol: 'none',
      stack: 'ci-band',
      data: lowerSeries,
      lineStyle: { opacity: 0 },
      z: 1,
      tooltip: { show: false },
    })
    series.push({
      name: '置信区间',
      type: 'line',
      symbol: 'none',
      stack: 'ci-band',
      data: bandSeries,
      lineStyle: { opacity: 0 },
      areaStyle: { color: 'rgba(250, 140, 22, 0.18)' },
      z: 1,
      tooltip: { show: false },
    })
  }

  const legendNames = ['历史数据', '预测数据']
  if (backtestMode) legendNames.push('实际数据')
  if (hasBand) legendNames.push('置信区间')

  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: {
      data: legendNames,
      top: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: 40, containLabel: true },
    xAxis: { type: 'category', data: allTimes, boundaryGap: false, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: unitText.value || '值', scale: true },
    series,
  }, true)
  chart.resize()
}

function handleResize(): void {
  chart?.resize()
  decompChart?.resize()
  cvChart?.resize()
}

// ===== STL 季节性分解 =====
async function onGenerateDecomp(): Promise<void> {
  if (!selectedDatasetId.value) return
  decompLoading.value = true
  decompData.value = null
  try {
    const res = await getDecomposition(selectedDatasetId.value)
    decompData.value = res
    if (res.success) {
      await nextTick()
      renderDecompChart()
    }
  } catch (e: any) {
    message.error(e.message || '分解失败')
  } finally {
    decompLoading.value = false
  }
}

function renderDecompChart(): void {
  if (!decompChartRef.value || !decompData.value) return
  if (!decompChart) {
    decompChart = echarts.init(decompChartRef.value)
  }
  const d = decompData.value
  const times = d.times || []
  const original = d.original || []
  const trend = d.trend || []
  const seasonal = d.seasonal || []
  const residual = d.residual || []

  // 4 个子图垂直排列，共享 x 轴
  const gridH = 25
  const gap = 4
  const grids: any[] = []
  const xAxes: any[] = []
  for (let i = 0; i < 4; i++) {
    grids.push({
      left: '8%', right: '3%',
      top: `${5 + i * (gridH + gap)}%`,
      height: `${gridH}%`,
    })
    xAxes.push({
      type: 'category',
      data: times,
      gridIndex: i,
      show: i === 3,
      axisLabel: { fontSize: 10 },
    })
  }

  decompChart.setOption({
    title: [
      { text: '原始数据', left: 'center', top: '2%', textStyle: { fontSize: 12 } },
      { text: '趋势分量', left: 'center', top: `${5 + gridH + gap}%`, textStyle: { fontSize: 12 } },
      { text: '季节分量', left: 'center', top: `${5 + 2 * (gridH + gap)}%`, textStyle: { fontSize: 12 } },
      { text: '残差分量', left: 'center', top: `${5 + 3 * (gridH + gap)}%`, textStyle: { fontSize: 12 } },
    ],
    tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: grids,
    xAxis: xAxes,
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true },
      { type: 'value', gridIndex: 1, scale: true },
      { type: 'value', gridIndex: 2, scale: true },
      { type: 'value', gridIndex: 3, scale: true },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2, 3], bottom: 0, height: 15 },
    ],
    series: [
      { name: '原始', type: 'line', data: original, xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, lineStyle: { width: 1.5 } },
      { name: '趋势', type: 'line', data: trend, xAxisIndex: 1, yAxisIndex: 1, showSymbol: false, lineStyle: { width: 2, color: '#fa8c16' } },
      { name: '季节', type: 'line', data: seasonal, xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, lineStyle: { width: 1.5, color: '#52c41a' } },
      { name: '残差', type: 'bar', data: residual, xAxisIndex: 3, yAxisIndex: 3, itemStyle: { color: '#bfbfbf' } },
    ],
  })
  decompChart.resize()
}

// ===== 交叉验证 MAE 图表 =====
function renderCVChart(): void {
  if (!cvChartRef.value || !cvResult.value) return
  if (!cvChart) {
    cvChart = echarts.init(cvChartRef.value)
  }
  const splits = cvResult.value.splits.filter((s) => s.status === 'success')
  const idxs = splits.map((s) => `切分${s.split_idx + 1}`)
  const maes = splits.map((s) => {
    const m = s.metrics as any
    return typeof m?.mae === 'number' ? m.mae : 0
  })
  const naiveMaes = splits.map((s) => {
    const m = s.metrics as any
    return m?.baselines?.naive_mae || 0
  })

  cvChart.setOption({
    title: { text: '各切分点 MAE 趋势', left: 'center', textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis' },
    legend: { data: ['模型MAE', 'Naive基线MAE'], bottom: 0 },
    grid: { left: '10%', right: '5%', top: '15%', bottom: '15%' },
    xAxis: { type: 'category', data: idxs },
    yAxis: { type: 'value', name: 'MAE' },
    series: [
      {
        name: '模型MAE',
        type: 'line',
        data: maes,
        smooth: true,
        lineStyle: { width: 2, color: '#1890ff' },
        itemStyle: { color: '#1890ff' },
        markLine: {
          data: [{ type: 'average', name: '平均' }],
          lineStyle: { color: '#1890ff', type: 'dashed' },
        },
      },
      {
        name: 'Naive基线MAE',
        type: 'line',
        data: naiveMaes,
        smooth: true,
        lineStyle: { width: 1.5, color: '#fa8c16', type: 'dashed' },
        itemStyle: { color: '#fa8c16' },
      },
    ],
  })
  cvChart.resize()
}

// ===== 统计模型预测 =====
async function onRunStatForecast(): Promise<void> {
  if (!selectedDatasetId.value) return
  runningStatForecast.value = true
  try {
    const res = await runStatisticalForecast({
      dataset_id: selectedDatasetId.value,
      horizon: horizon.value,
      model_type: selectedStatModel.value,
      start_index: predictMode.value === 'backtest' ? startIndex.value : null,
      use_covariates: (selectedStatModel.value === 'arima' || selectedStatModel.value === 'prophet') && useCovariates.value,
    })
    // 用结果更新趋势数据中的预测信息（forecastInfo 为 computed，需更新 trendData）
    if (trendData.value) {
      trendData.value = {
        ...trendData.value,
        forecast: {
          forecasts: res.result.forecasts,
          quantiles: res.result.quantiles,
          future_times: res.result.future_times,
          actuals: res.result.actuals || [],
          metrics: res.result.metrics || {},
          model_name: res.result.model_name,
          duration_ms: res.task.duration_ms,
          analysis: res.result.analysis,
          task_id: res.task.id,
          start_index: res.task.start_index,
          horizon: res.task.horizon,
          is_backtest: res.task.start_index !== null && res.task.start_index !== undefined,
        },
      }
    }
    analysisText.value = res.result.analysis || ''
    // 刷新图表
    await nextTick()
    renderChart()
    // 刷新任务列表
    if (selectedDatasetId.value) fetchTasks(selectedDatasetId.value)
    message.success(`${selectedStatModel.value.toUpperCase()} 统计模型预测完成`)
  } catch (e: any) {
    message.error(e.message || '统计模型预测失败')
  } finally {
    runningStatForecast.value = false
  }
}

// ===== 辅助 =====
function formatTime(s: string): string {
  return s ? s.replace('T', ' ').slice(0, 19) : ''
}
function statusText(s: string): string {
  const map: Record<string, string> = { pending: '等待', running: '运行中', success: '成功', failed: '失败' }
  return map[s] || s
}
function statusColor(s: string): string {
  const map: Record<string, string> = { pending: 'default', running: 'processing', success: 'green', failed: 'red' }
  return map[s] || 'default'
}

// ==================== B1: 自动模型选择 ====================
const autoSelecting = ref(false)
const autoSelectDrawerVisible = ref(false)
const autoSelectResult = ref<any>(null)

async function onAutoSelect() {
  if (!selectedDatasetId.value) return
  autoSelecting.value = true
  autoSelectDrawerVisible.value = true
  try {
    const res = await autoSelectModel({
      dataset_id: selectedDatasetId.value,
      horizon: horizon.value,
      n_splits: 3,
    })
    autoSelectResult.value = res
    if (res?.best_model?.model_name) {
      message.success(res.best_model.recommendation)
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    autoSelecting.value = false
  }
}

// ==================== B2: 集成预测 ====================
const ensembling = ref(false)

async function onEnsembleForecast() {
  if (!selectedDatasetId.value) return
  ensembling.value = true
  try {
    const res = await ensembleForecast({
      dataset_id: selectedDatasetId.value,
      horizon: horizon.value,
      start_index: predictMode.value === 'backtest' ? startIndex.value : null,
      strategy: 'weighted_avg',
    })
    if (res?.result && trendData.value) {
      const t = res.task
      const r = res.result
      trendData.value.forecast = {
        forecasts: r.forecasts,
        quantiles: r.quantiles,
        future_times: r.future_times,
        actuals: r.actuals || [],
        metrics: r.metrics || {},
        model_name: r.model_name,
        duration_ms: t.duration_ms,
        analysis: r.analysis,
        task_id: t.id,
        start_index: t.start_index,
        horizon: t.horizon,
        is_backtest: t.start_index != null,
      }
      analysisText.value = r.analysis || ''
      await nextTick()
      renderChart()
      const successCount = res.member_results?.filter((m: any) => m.status === 'success').length || 0
      message.success(`集成预测完成：${successCount} 个模型参与`)
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    ensembling.value = false
  }
}

// ==================== B3: 高级特征工程 ====================
const featuresDrawerVisible = ref(false)
const featuresLoading = ref(false)
const featuresResult = ref<any>(null)

const featuresPreviewColumns = computed(() => {
  if (!featuresResult.value?.feature_names) return []
  return [
    { title: '索引', key: 'idx', width: 60, customRender: ({ index }: any) => index },
    ...featuresResult.value.feature_names.map((name: string) => ({
      title: name,
      dataIndex: name,
      key: name,
      width: 120,
    })),
  ]
})

const featuresPreviewData = computed(() => {
  if (!featuresResult.value?.features) return []
  const feats = featuresResult.value.features
  const names = featuresResult.value.feature_names
  const n = names.length > 0 ? feats[names[0]]?.length || 0 : 0
  const rows: any[] = []
  for (let i = 0; i < Math.min(10, n); i++) {
    const row: any = { key: i }
    for (const name of names) {
      const val = feats[name]?.[i]
      row[name] = val !== undefined ? Number(val).toFixed(4) : '-'
    }
    rows.push(row)
  }
  return rows
})

async function onFeaturesDrawerOpen() {
  if (!selectedDatasetId.value || featuresResult.value) return
  featuresLoading.value = true
  try {
    featuresResult.value = await getAdvancedFeatures(selectedDatasetId.value)
  } catch {
    // 错误已由拦截器提示
  } finally {
    featuresLoading.value = false
  }
}

// ==================== B4: 异常检测 ====================
const anomalyDrawerVisible = ref(false)
const anomalyLoading = ref(false)
const anomalyMethod = ref<'stl_residual' | 'isolation_forest' | 'change_point'>('stl_residual')
const anomalyResult = ref<any>(null)

async function onDetectAnomalies() {
  if (!selectedDatasetId.value) return
  anomalyLoading.value = true
  try {
    anomalyResult.value = await detectAnomalies({
      dataset_id: selectedDatasetId.value,
      method: anomalyMethod.value,
    })
    if (anomalyResult.value?.anomaly_indices?.length) {
      message.success(`检测到 ${anomalyResult.value.anomaly_indices.length} 个异常点`)
    } else {
      message.info('未检测到异常点')
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    anomalyLoading.value = false
  }
}

// ==================== B5: 超参优化 ====================
const optimizing = ref(false)

async function onOptimizeParams() {
  if (!selectedDatasetId.value) return
  // 使用当前选中的统计模型，默认 arima
  const modelType = selectedStatModel.value === 'prophet' ? 'prophet'
    : selectedStatModel.value === 'ets' ? 'ets'
    : selectedStatModel.value === 'theta' ? 'theta'
    : 'arima'

  if (modelType === 'theta') {
    message.info('Theta 为标准实现，无可调超参')
    return
  }

  optimizing.value = true
  try {
    const res = await optimizeParams({
      dataset_id: selectedDatasetId.value,
      model_type: modelType as any,
      horizon: horizon.value,
      n_trials: 20,
    })
    if (res?.best_params && Object.keys(res.best_params).length > 0) {
      message.success(`最优参数: ${JSON.stringify(res.best_params)}，MAE=${res.best_mae}`)
    } else {
      message.info(res?.summary || '未找到有效参数')
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    optimizing.value = false
  }
}

// ===== 生命周期 =====
watch(
  () => modelStatus.value.forecast,
  () => { /* 触发响应式更新 */ }
)

onMounted(async () => {
  await Promise.all([
    appStore.loadModelStatus(),
    fetchForecastModels(),
    fetchDatasets(),
  ])
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
  decompChart?.dispose()
  decompChart = null
  cvChart?.dispose()
  cvChart = null
})
</script>

<style scoped>
.trends-page {
  max-width: 1400px;
  margin: 0 auto;
}

.chart-container {
  width: 100%;
  height: 420px;
}

.decomp-chart-container {
  height: 500px;
  width: 100%;
}

.decomp-info {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 8px;
  padding: 8px 0 0;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.65);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.dot.history {
  background: #1677ff;
}

.dot.forecast {
  background: #fa8c16;
}

.dot.actual {
  background: #52c41a;
}

.dot.label {
  background: #faad14;
}

.band {
  display: inline-block;
  width: 18px;
  height: 10px;
  background: rgba(250, 140, 22, 0.35);
  border: 1px solid #fa8c16;
}

.stat-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.stat-row span {
  color: rgba(0, 0, 0, 0.55);
}

.stat-row b {
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
}

.text-up {
  color: #52c41a;
}

.text-down {
  color: #f5222d;
}

.text-warn {
  color: #faad14;
}

.param-label {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.param-hint {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

/* 小卡片样式（统一尺寸） */
.mini-card {
  position: relative;
  overflow: hidden;
  height: 100%;
}

.mini-card :deep(.ant-card-body) {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 96px;
  box-sizing: border-box;
}

.mini-card :deep(.ant-statistic) {
  flex: 1;
  min-width: 0;
}

.mini-card :deep(.ant-statistic-title) {
  font-size: 12px;
  margin-bottom: 4px;
  color: rgba(0, 0, 0, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-card :deep(.ant-statistic-content) {
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  flex-shrink: 0;
}

.mini-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mini-label {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-value {
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
  line-height: 1.4;
  word-break: break-all;
}

.kpi-blue { background: #1677ff; }
.kpi-cyan { background: #13c2c2; }
.kpi-green { background: #52c41a; }
.kpi-red { background: #f5222d; }
.kpi-orange { background: #fa8c16; }
.kpi-purple { background: #722ed1; }
.kpi-gray { background: #8c8c8c; }
.kpi-warn { background: #faad14; }

.kpi-highlight {
  border-left: 3px solid #faad14;
}

/* 长文本摘要卡片 */
.long-summary {
  width: 100%;
}

.long-summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.8;
}

.long-summary-meta .meta-item {
  white-space: nowrap;
}

.long-summary-meta .meta-item b {
  color: rgba(0, 0, 0, 0.45);
  font-weight: 500;
  margin-right: 4px;
}

.long-summary-text {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.75);
  line-height: 1.8;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.analysis-report {
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 16px 20px;
}

.analysis-report pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.8;
  color: rgba(0, 0, 0, 0.85);
}

/* 交叉验证抽屉 */
.cv-config {
  margin-bottom: 4px;
}

.cv-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.8;
}

.cv-summary .meta-item {
  white-space: nowrap;
}

.cv-summary .meta-item b {
  color: rgba(0, 0, 0, 0.45);
  font-weight: 500;
  margin-right: 4px;
}

.cv-section-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.75);
  margin-top: 12px;
  margin-bottom: 4px;
}

.cv-chart-container {
  height: 280px;
  width: 100%;
  margin-bottom: 16px;
}

.cv-metrics-table,
.compare-table {
  margin-top: 12px;
}

.cv-split-table {
  margin-top: 16px;
}

.best-model-alert {
  margin-bottom: 12px;
}

/* 多模型对比 */
.compare-baselines {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  line-height: 1.8;
  margin-bottom: 12px;
}

.compare-baselines .meta-item {
  white-space: nowrap;
}

.compare-baselines .meta-item b {
  color: rgba(0, 0, 0, 0.45);
  font-weight: 500;
  margin-right: 4px;
}

/* 最优模型行高亮 */
:deep(.best-model-row) {
  background-color: #f6ffed;
}

:deep(.best-model-row:hover > td) {
  background-color: #d9f7be !important;
}
</style>
