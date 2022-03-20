import { FilterDropdown, List, Select, Table, useTable } from "@pankod/refine-antd";
import { IPocketArticle } from "interfaces";

export const PocketArticleList: React.FC = () => {
	const { tableProps } = useTable<IPocketArticle>();

  return (
    <List>
      <Table {...tableProps} rowKey="id">
        <Table.Column dataIndex="given_title" title="given_title" />
        <Table.Column dataIndex="resolved_title" title="resolved_title" />
        <Table.Column dataIndex="status" title="status" filterDropdown={(props) => (
          // note that this does server-side filtering
          // so the API needs to be able to handle the query parameter "status=<status_code>"
          <FilterDropdown {...props}>
            <Select
              style={{ minWidth: 200 }}
              mode="multiple"
              placeholder="Select Status"
              options={[
                { label: "0", value: 0 },
                { label: "1", value: 1 },
                { label: "2", value: 2 },
              ]}
            />
          </FilterDropdown>
        )} 
        />
      </Table>
    </List>
  );
};