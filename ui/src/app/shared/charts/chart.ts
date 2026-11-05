import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import type { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';

/** An ngx-echarts chart sized by `height`; the options come from chart-options.ts. */
@Component({
  selector: 'app-chart',
  imports: [NgxEchartsDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'block' },
  template: `
    <div
      echarts
      [options]="options()"
      [autoResize]="true"
      class="w-full"
      [style.height]="height()"
      role="img"
      [attr.aria-label]="label()"
    ></div>
  `,
})
export class Chart {
  readonly options = input.required<EChartsCoreOption>();
  readonly label = input.required<string>();
  readonly height = input('20rem');
}
