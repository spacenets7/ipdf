import json
from pydantic import BaseModel,Field
from typing import Literal
from app.schema import Chart,Series,CellRef,parse_number
from app.generate.common import generate,provenance


class ChartPlan(BaseModel):
    usable: bool
    type: Literal['bar','line']='bar'
    title: str=Field(max_length=200)
    label_column: int=Field(ge=0)
    header_row: int=Field(ge=0)
    value_columns: list[int]=Field(max_length=5)
    data_rows: list[int]=Field(max_length=30)


def build(table,section,level,paper_id):
    def validate(plan):
        if not plan.usable:
            return
        if not plan.data_rows or not plan.value_columns:
            raise ValueError('A usable chart requires data rows and numeric columns')
        if len(set(plan.data_rows))!=len(plan.data_rows) or len(set(plan.value_columns))!=len(plan.value_columns):
            raise ValueError('Duplicate row/column references')
        for row in plan.data_rows:
            for col in plan.value_columns:
                try:
                    value=parse_number(table.cells[row][col])
                    label=table.cells[row][plan.label_column]
                    header=table.cells[plan.header_row][col]
                except IndexError:
                    raise ValueError('Table coordinate is out of bounds')
                if value is None or not label or not header:
                    raise ValueError('Only unambiguous numeric cells with source labels can be charted')
    result=generate(ChartPlan,'charts',section,level,paper_id+':'+table.id,
        'Extract a chart plan from this ORIGINAL table grid. Return ROW/COLUMN INDICES ONLY, not plotted values. '
        'Choose comparable measurements with the same units. Do not mix years, sample sizes and metric values. '
        'Indices are zero-based. Set usable=false if this grid is unreliable, not numeric, or units are incomparable. '
        'Use a source header and row labels verbatim. TABLE '+table.label+':\n'+json.dumps(table.cells),
        backend='DEEP',validator=validate,ground=False)
    return from_plan(table,result.value,result)


def from_plan(table,plan,result):
    """Pure evidence mapping, independently testable against real PDF cells."""
    if not plan.usable:
        return []
    series=[]
    for col in plan.value_columns:
        series.append(Series(name=str(table.cells[plan.header_row][col]),
            labels=[str(table.cells[r][plan.label_column]) for r in plan.data_rows],
            values=[parse_number(table.cells[r][col]) for r in plan.data_rows],
            source_cells=[CellRef(row=r,column=col) for r in plan.data_rows]))
    return [Chart(id=table.id+'-chart',type=plan.type,title=plan.title,page=table.page,series=series,
        source_table=table.id,caption=f'from {table.label}, p.{table.page}',generated_by=provenance('charts',table.page,result))]
