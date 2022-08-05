#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time   : 2022-08-05 11:10:57
# @Author : 七月


import allure
import pytest
from common.setting import ConfigHandler
from utils.read_files_tools.get_yaml_data_analysis import CaseData
from utils.assertion.assert_control import Assert
from utils.requests_tool.request_control import RequestControl
from utils.read_files_tools.regular_control import regular
from utils.requests_tool.teardown_control import TearDownHandler


TestData = CaseData(ConfigHandler.data_path + r'Collect/collect_update_tool.yaml').case_process()
re_data = regular(str(TestData))


@allure.epic("开发平台接口")
@allure.feature("收藏模块")
class TestCollectUpdateTool:

    @allure.story("编辑收藏网址接口")
    @pytest.mark.parametrize('in_data', eval(re_data), ids=[i['detail'] for i in TestData])
    def test_collect_update_tool(self, in_data, case_skip):
        """
        :param :
        :return:
        """
        res = RequestControl().http_request(in_data)
        TearDownHandler().teardown_handle(res)
        Assert(in_data['assert_data']).assert_equality(response_data=res['response_data'],
                                                       sql_data=res['sql_data'], status_code=res['status_code'])


if __name__ == '__main__':
    pytest.main(['test_collect_update_tool.py', '-s', '-W', 'ignore:Module already imported:pytest.PytestWarning'])
