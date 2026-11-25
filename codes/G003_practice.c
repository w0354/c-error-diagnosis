#include <stdio.h>
int main(void)
{
char ch = 'C';
int n = 3;
printf("%d\n", ch);
printf("%d\n", n);
return 0;
}
题2（变量声明类型）：
#include <stdio.h>
int main(void)
{
int price = 9.9;
printf("%d\n", price);
return 0;
}
题3（初始化位置）：
#include <stdio.h>
int main(void)
{
int i, sum = 0;
for (i = 1; i <= 3; i++)
{
sum = 0;
sum += i;
}
printf("%d\n", sum);
return 0;
}
